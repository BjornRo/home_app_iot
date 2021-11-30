from configparser import ConfigParser
from threading import Thread
import socket
from datetime import datetime, timedelta
from time import sleep
from typing import Union
import redis
from redis.commands.json import JSON as REJSON_Client
from zlib import decompress, compress
from bcrypt import checkpw
from ast import literal_eval
import logging
import traceback
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

# Socket info constants.
MAX_PAYLOAD_SOCKET = 2048

# Socket setup
S_PORT = 42661

# TODO real implementation.
# {IP: Datetime(bantime)}
timeout_dict = {}
BANTIME = 30  # minutes


# TODO ADD REJSON


def main():
    device_credentials = get_default_credentials()

    socket_handler(device_credentials, None)


def socket_handler(device_cred: dict, mc_local):
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as srv:
        socket.setdefaulttimeout(2)  # For ssl handshake and auth.
        srv.bind(("", S_PORT))
        srv.listen(8)
        with context.wrap_socket(srv, server_side=True) as sslsrv:
            while 1:
                try:
                    # if timeout, client is not connected.
                    client, (c_ip, c_port) = sslsrv.accept()
                    bantime: datetime | None
                    if bantime := timeout_dict.get(c_ip):
                        if datetime.now() > bantime:
                            timeout_dict.pop(c_ip)
                        else:
                            logging.warning(f"{timenow()} > Tmp banned ip tried to connect: {c_ip}:{c_port}")
                            client.close()
                            continue
                    Thread(target=client_handler, args=(device_cred, client), daemon=True).start()
                except Exception as e:  # Don't care about faulty clients with no SSL wrapper.
                    logging.info(timenow() + " > Client tried to connect without SSL context: " + str(e))


def validate_time(prev_datetime, time) -> Union[datetime, None]:
    try:  # All exceptions should be silenced.
        if prev_datetime < (dt := datetime.fromisoformat(time)):
            return dt
    except:
        pass
    return None


def client_handler(device_cred: dict[str, bytes], client: ssl.SSLSocket) -> None:
    # No need for contex-manager due to always trying to close conn at the end.
    try:  # First byte msg len => read rest of msg => parse and validate.
        device_name = validate_user(device_cred, recvall(client, ord(client.recv(1))))
        if device_name is None:
            global timeout_dict  # TODO
            timeout_dict[client.getpeername()[0]] = datetime.now() + timedelta(minutes=BANTIME)
            return
        client.send(b"OK")

        # TODO to be removed when I start refactoring remote nodes.
        # Now just gets data and continues. This step can be removed.
        # If I want status, I'll add it as a json from webapp.
        recvdata = client.recv(1)

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
            except:  # Test if data is compressed, else it is not -> ignore.
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
            if not test_value(data_key, value, 100):
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


def validate_user(device_cred: dict[str, bytes], data: bytes) -> str | None:
    # dataform: b"login\npassw", data may be None -> Abuse try except...
    try:
        # Malformed if 2 splits. Faster to raise except than test pw.
        device_name, passwd = data.split(b'\n', 2)
        device_name = device_name.decode()
        hash_passwd = device_cred.get(device_name)
        if hash_passwd is None:
            logging.warning(timenow() + " > An unknown entity tried to connect:" + device_name)
        elif checkpw(passwd, hash_passwd):
            return device_name
    except UnicodeDecodeError as e:
        logging.warning(timenow() + " > Device name was not in utf8 codec: " + str(e))
    except ValueError as e:
        logging.warning(timenow() + " > Password check failed: " + str(e))
    return None


def test_value(key: str, value: int | float, magnitude: int = 1) -> bool:
    try:  # Anything that isn't a number will be rejected by try.
        value *= magnitude
        match key.lower():
            case "temperature":
                return -5000 <= value <= 6000
            case "humidity":
                return 0 <= value <= 10000
            case "airpressure":
                return 90000 <= value <= 115000
    except:
        logging.warning(timenow() + " > Bad key in data.")
    return False


def get_default_credentials() -> dict[str, bytes]:
    USERS = ConfigParser()
    USERS.read("users.ini")
    return {usr: USERS[usr]["password"].encode() for usr in USERS.sections()}


def timenow() -> str:
    return datetime.now().isoformat("T")


if __name__ == "__main__":
    main()
