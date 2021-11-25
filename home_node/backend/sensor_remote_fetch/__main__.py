from configparser import ConfigParser
from threading import Thread, Semaphore
from datetime import datetime
from time import sleep
from typing import Union
from pymemcache.client.base import PooledClient
from bcrypt import checkpw
from ast import literal_eval
import traceback

import schedule
import json
import ssl
import sys

# Replace encoder to not use white space. Default to use isoformat for datetime =>
#   Since I know the types I'm dumping. If needed custom encoder or an "actual" default function.
json._default_encoder = json.JSONEncoder(  # type: ignore
    separators=(",", ":"), default=lambda dt: dt.isoformat())

# Some imports are put into the function that require that module.
#   These modules are loaded before function-loop.

# Idea is to keep this as threading and remote_docker/sensor_logger as asyncio
# This is to compare the flavours of concurrency.

# MISC
MINOR_KEYS = ("Temperature", "Humidity", "Airpressure")

# Config reader -- Path(__file__).parent.absolute() /
CFG = ConfigParser()
CFG.read("config.ini")
JSONDATAFILE = "remotedata.json"

# SSL Context
HOSTNAME = CFG["CERT"]["url"]
SSLPATH = f"/etc/letsencrypt/live/{HOSTNAME}/"
SSLPATH_TUPLE = (SSLPATH + "fullchain.pem", SSLPATH + "privkey.pem")
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(*SSLPATH_TUPLE)

# Token for an eventual use.
USER = CFG["TOKEN"]["user"]
TOKEN = CFG["TOKEN"]["token"]

# Socket info constants.
COMMAND_LEN = 1
MAX_PAYLOAD_SOCKET = 2048
#DEV_NAME_LEN = int(CFG["TOKEN"]["dev_name_len"])

# Socket setup
S_PORT = 42661

# Datastructure is in the form of:
#  devicename/measurements: for each measurement type: value.
# New value is a flag to know if value has been updated since last SQL-query. -> Each :00, :30


def main():
    main_node_data = {
        "home": {
            "bikeroom/temp": {"Temperature": -99},
            "balcony/temphumid": {"Temperature": -99, "Humidity": -99},
            "kitchen/temphumidpress": {"Temperature": -99, "Humidity": -99, "Airpressure": -99},
        }
    }
    device_login = {USER: TOKEN.encode()}
    # Read data file. Adds the info for remote devices.
    with open(JSONDATAFILE, "r") as f:
        for mainkey, mainvalue in json.load(f).items():
            device_login[mainkey] = mainvalue.pop("password").encode()
            main_node_data[mainkey] = mainvalue

    # Associated dict to see if the values has been updated. This is to let remote nodes
    # just send data and then you can decide at the main node.
    main_node_new_values = {
        sub_node: {device: False for device in sub_node_data}
        for sub_node, sub_node_data in main_node_data.items()
    }

    # Setup memcache and set initial values for memcached.
    class JSerde(object):
        def serialize(self, key, value):
            return json.dumps(value), 2

    memcache_local = PooledClient(
        "memcached:11211", serde=JSerde(), max_pool_size=2)
    for key in main_node_data.keys():
        memcache_local.set("weather_data_" + key, main_node_data[key])

    # Semaphores to stop race conditions due to threading.
    # Each node gets its "own" semaphore since the nodes don't interfere with eachother
    # Before SQL Queries, all locks are acquired since this is a read/write situation.
    lock = Semaphore(len(main_node_data))
    Thread(
        target=mqtt_agent,
        args=(
            main_node_data["home"],
            main_node_new_values["home"],
            memcache_local,
            lock,
        ),
        daemon=True,
    ).start()
    Thread(
        target=data_socket,
        args=(
            main_node_data,
            main_node_new_values,
            device_login,
            memcache_local,
            lock,
        ),
        daemon=True,
    ).start()
    schedule_setup(main_node_data, main_node_new_values, lock)

    # Poll tmpdata until all Nones are gone.
    while 1:
        sleep(1)
        for sub_node_values in main_node_data["home"].values():
            if -99 in sub_node_values.values():
                break
        else:
            break

    while 1:
        schedule.run_pending()
        sleeptime = schedule.idle_seconds()
        if sleeptime > 0:
            sleep(sleeptime)  # type: ignore


def data_socket(main_node_data, main_node_new_values, device_login, mc_local, lock):
    time_last_update = {
        sub_node: {device: datetime.min for device in sub_node_data}
        for sub_node, sub_node_data in main_node_data.items()
        if sub_node != "home"
    }
    # Might refactor into 'user' have allowed methods, (P,G..)
    denylist = (b"getstatus",)

    def validate_time(prev_datetime, time) -> Union[datetime, None]:
        try:  # All exceptions should be silenced.
            if prev_datetime < (dt := datetime.fromisoformat(time)):
                return dt
        except:
            pass
        return None

    def parse_and_update(device_name: str, payload: str) -> None:
        update_cache = False
        try:  # First test if it's a valid json object
            data = json.loads(payload)
        except:  # Else fallback to literal eval
            data = literal_eval(payload)

        if isinstance(data, dict):
            data = data.items()
        elif isinstance(data, (list, tuple)):
            if not isinstance(data[0], (list, tuple)):
                raise Exception("Parsed data is not a list of lists.")
        else:
            return
        for device_key, (time, data) in data:
            dt_time = validate_time(
                time_last_update[device_name][device_key], time)
            if dt_time is None:
                continue
            iter_obj = get_iterable(
                data, main_node_data[device_name][device_key])
            if iter_obj is None:
                continue
            tmpdata = {}
            for data_key, value in iter_obj:
                if not _test_value(data_key, value, 100):
                    break
                tmpdata[data_key] = value
            else:
                with lock:
                    main_node_data[device_name][device_key] |= tmpdata
                    main_node_new_values[device_name][device_key] = True
                time_last_update[device_name][device_key] = dt_time
                update_cache = True
        if update_cache:
            mc_local.set(
                f"weather_data_{device_name}_time", time_last_update[device_name])
            mc_local.set("weather_data_" + device_name,
                         main_node_data[device_name])

    def recvall(client, size, buf_size=4096):
        received_chunks = []
        remaining = size
        while remaining > 0:
            received = client.recv(min(remaining, buf_size))
            if not received:
                return b''
            received_chunks.append(received)
            remaining -= len(received)
        return b''.join(received_chunks)

    def parse_validate(data: bytes):
        # dataform: b"login\npassw", data may be None -> Abuse try except...
        try:
            # Malformed if 2 splits. Faster to raise except than test pw.
            device_name, passw = data.split(b'\n', 2)
            device_name = device_name.decode()
            if checkpw(passw, device_login[device_name]):
                return device_name
        except:
            pass
        return None

    def client_handler(client: ssl.SSLSocket):
        # No need for contex-manager due to always trying to close conn at the end.
        try:  # First byte msg len => read rest of msg => parse and validate.
            device_name = parse_validate(recvall(client, ord(client.recv(1))))
            if device_name is None:
                return
            client.send(b"OK")
            # Decide what the client wants to do.
            recvdata = client.recv(COMMAND_LEN)
            if recvdata == b"G":  # [G]ET
                to_send = json.dumps(
                    (main_node_data, time_last_update)).encode()
                return client.sendall(compress(to_send))
            if device_name in denylist:
                return
            if recvdata == b"P":  # [P]OST
                pass
            else:
                return

            # POST => Notify that it is ok to send data now. Change timeout to keep connection alive.
            client.settimeout(60)
            client.send(b"OK")
            # While connection is alive, send data. If connection is lost, then an
            # exception may be thrown and the while loop exits, and thread is destroyed.
            while 1:
                payload_len = int.from_bytes(recvall(client, 3, 3), 'big')
                # Calculate header length.
                if not (0 < payload_len <= MAX_PAYLOAD_SOCKET):
                    break
                recvdata = recvall(client, payload_len, MAX_PAYLOAD_SOCKET)
                if not recvdata:
                    break
                try:
                    recvdata = decompress(recvdata)
                except:
                    pass
                parse_and_update(device_name, recvdata.decode())
        except (TypeError,):  # This should never happen.
            traceback.print_exc()
        except (socket.timeout,):  # This will happen alot. Don't care
            pass
        except Exception as e:  # Just to log if any less important exceptions are raised
            print(e, file=sys.stderr)
        finally:
            try:
                client.close()
            except:
                pass

    import socket
    from zlib import decompress, compress

    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as srv:
        socket.setdefaulttimeout(2)  # For ssl handshake and auth.
        srv.bind(("", S_PORT))
        srv.listen(8)
        with context.wrap_socket(srv, server_side=True) as sslsrv:
            while 1:
                try:
                    # if timeout, client is not connected.
                    client = sslsrv.accept()[0]
                    # Spawn a new thread.
                    Thread(target=client_handler, args=(
                        client,), daemon=True).start()
                except:  # Don't care about faulty clients with no SSL wrapper.
                    pass

# mqtt function does all the heavy lifting sorting out bad data.
def schedule_setup(main_node_data: dict, main_node_new_values: dict, lock: Semaphore):
    def querydb():
        update_node = [s_node for s_node,
                       nv in main_node_new_values.items() if any(nv.values())]
        if not update_node:
            return

        # Copy data and set values to false.
        time_now = datetime.now().isoformat("T", "minutes")
        new_data = {}
        # Acquire all semaphores
        for _ in range(len(main_node_data)):
            lock.acquire()
        for sub_node in update_node:
            new_data[sub_node] = []
            for device, new_value in main_node_new_values[sub_node].items():
                if new_value:
                    main_node_new_values[sub_node][device] = False
                    new_data[sub_node].append(
                        (device, main_node_data[sub_node][device].copy()))
        # Release all semaphores when done. All values are tested to be valid in _test_value().
        # If main crashes for some unknown reason, all threads dies due to daemon. No deadlocks...
        lock.release(len(main_node_data))
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO Timestamp VALUES ('{time_now}')")
        for sub_node_data in new_data.values():
            for device, device_data in sub_node_data:
                mkey = device.split("/")[0]
                for table, value in device_data.items():
                    cursor.execute(
                        f"INSERT INTO {table} VALUES ('{mkey}', '{time_now}', {value})")
        db.commit()
        cursor.close()

    def reload_ssl():
        context.load_cert_chain(*SSLPATH_TUPLE)

    import sqlite3

    db = sqlite3.connect("/db/main_db.db")

    # Due to the almost non-existing concurrency, just keep conn alive.
    schedule.every().hour.at(":30").do(querydb)
    schedule.every().hour.at(":00").do(querydb)
    schedule.every().day.at("23:45").do(reload_ssl)


def mqtt_agent(h_tmpdata: dict, h_new_values: dict, memcache, lock):
    def on_connect(client, *_):
        for topic in list(h_tmpdata.keys()) + [status_path]:
            client.subscribe("home/" + topic)

    def on_message(client, userdata, msg):
        try:  # Get values into a listlike form - Test valid payload.
            listlike = literal_eval(msg.payload.decode())
            if isinstance(listlike, (tuple, dict, list)):
                pass
            elif isinstance(listlike, (int, float)):
                listlike = (listlike,)
            else:  # Unknown type.
                return
        except:
            return

        # Handle the topic depending on what it is about.
        topic = msg.topic.replace("home/", "")
        if status_path == topic:  # Test topic. Remove all 0,1. Set should be empty to be valid.
            if not set(listlike).difference(set((0, 1))) and len(listlike) == 4:
                memcache.set("relay_status", listlike)
            return
        iter_obj = get_iterable(listlike, h_tmpdata[topic])
        if iter_obj is None:
            return
        tmpdict = {}
        for key, value in iter_obj:
            # If a device sends bad data -> break and discard, else update
            if not _test_value(key, value):
                break
            tmpdict[key] = value / 100
        else:
            memcache.set("weather_data_home", h_tmpdata)
            with lock:
                h_tmpdata[topic] |= tmpdict
                h_new_values[topic] = True

    from paho.mqtt.client import Client

    # Setup and connect mqtt client. Return client object.
    status_path = "balcony/relay/status"
    mqtt = Client("br_logger")
    mqtt.on_connect = on_connect
    mqtt.on_message = on_message
    while True:
        try:  # Wait until mqtt server is connectable. No need to read exceptions here.
            if mqtt.connect("mqtt", 1883, 60) == 0:
                break
        except:
            pass
        sleep(5)
    mqtt.loop_forever()


def get_iterable(recvdata: Union[dict, list, tuple], maindata: dict):
    if isinstance(recvdata, dict) and recvdata.keys() == maindata.keys():
        return recvdata.items()
    if isinstance(recvdata, (tuple, list)) and len(recvdata) == len(maindata):
        return zip(MINOR_KEYS, recvdata)
    return None


def _test_value(key: str, value: Union[int, float], magnitude: int = 1) -> bool:
    try:  # Anything that isn't a number will be rejected by try.
        value *= magnitude
        if key == "Temperature":
            return -5000 <= value <= 6000
        elif key == "Humidity":
            return 0 <= value <= 10000
        elif key == "Airpressure":
            return 90000 <= value <= 115000
    except:
        pass
    return False


if __name__ == "__main__":
    main()
