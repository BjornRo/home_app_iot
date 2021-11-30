from configparser import ConfigParser
from threading import Thread
import socket
from datetime import datetime, timedelta
from time import sleep
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


# Config reader -- Path(__file__).parent.absolute() /
CFG = ConfigParser()
CFG.read("config.ini")

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
BAN_TIME = 30  # minutes
MAX_ATTEMPTS = 10

# MISC
MINOR_KEYS = ("temperature", "humidity", "airpressure")
MQTT_HOST = "home.1d"
REJSON_HOST = "rejson"


def main():
    r_conn: REJSON_Client = redis.Redis(host=REJSON_HOST, port=6379, db=0).json()  # type: ignore
    device_credentials = get_default_credentials()
    socket_handler(device_credentials, r_conn)


def socket_handler(device_cred: dict, r_conn: REJSON_Client):
    def is_client_allowed(block_dict: dict[str, dict], ip_addr: str, port):
        bantime: datetime
        user_data = block_dict.get(ip_addr)
        if user_data is not None:
            bantime = user_data.get("time")  # type:ignore
            if datetime.now() > bantime:
                block_dict.pop(ip_addr)
            else:
                attempts: int = user_data["attempts"] + 1
                if attempts >= MAX_ATTEMPTS:
                    user_data["bantime"] = datetime.now() + timedelta(minutes=BAN_TIME*attempts*5)
                    attempts -= 1
                elif attempts >= MAX_ATTEMPTS/2:
                    user_data["bantime"] = datetime.now() + timedelta(minutes=BAN_TIME*attempts*2)
                user_data["attempts"] = attempts
                logging.warning(f"{timenow()} > Tmp banned ip tried to connect: {ip_addr}:{port}")
                return False
        return True

    block_dict = {}
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as srv:
        socket.setdefaulttimeout(3)  # For ssl handshake and auth.
        srv.bind(("", S_PORT))
        srv.listen(8)
        with context.wrap_socket(srv, server_side=True) as sslsrv:
            while 1:
                try:
                    # if timeout, client is not connected.
                    client, (c_ip, c_port) = sslsrv.accept()
                    if is_client_allowed(block_dict, c_ip, c_port):
                        Thread(target=client_handler, args=(block_dict, r_conn, device_cred, client), daemon=True).start()
                except Exception as e:  # Don't care about faulty clients with no SSL wrapper.
                    logging.info(timenow() + " > Client tried to connect without SSL context: " + str(e))


def client_handler(block_dict: dict[str, dict], r_conn: REJSON_Client, device_cred: dict[str, bytes], client: ssl.SSLSocket) -> None:
    def recvall(client:  ssl.SSLSocket, size, buf_size=4096) -> bytes:
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

    # No need for contex-manager due to always trying to close conn at the end.
    try:  # First byte msg len => read rest of msg => parse and validate.
        location_name = validate_user(device_cred, recvall(client, ord(client.recv(1))))
        if location_name is None:
            block_dict[client.getpeername()[0]] = {"time": datetime.now() + timedelta(minutes=BAN_TIME), "attempts": 1}
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
            except:  # Test if data is compressed, else it is not -> ignore.
                pass
            if not parse_and_update(r_conn, location_name, recvdata.decode()):
                break
    except (TypeError,):  # This should never happen.
        traceback.print_exc()
    except (socket.timeout,) as e:  # This will happen alot. Don't care
        logging.info(timenow() + " > Socket timeout: " + str(e))
    except Exception as e:  # Just to log if any less important exceptions are raised
        logging.info(timenow() + " > Exception from client handler: " + str(e))
    try:
        client.close()
    except:
        pass


def parse_and_update(r_conn: REJSON_Client, location_name: str, payload: str) -> bool:
    def validate_time(r_conn: REJSON_Client, r_conn_path: str, new_time: str) -> datetime | None:
        try:
            new_dt = datetime.fromisoformat(new_time)
            old_time: str | None = r_conn.get("sensors", r_conn_path)
            if old_time is None:
                set_json(r_conn, r_conn_path, new_dt)
                return new_dt
            old_dt = datetime.fromisoformat(old_time)
            if old_dt < new_dt:
                return new_dt
            else:
                logging.info(timenow() + " > Old data sent: " + new_time)
        except Exception as e:
            logging.info(timenow() + " > Time validation failed: " + str(e))
        except ValueError as e:
            logging.info(timenow() + " > Time conversion (str -> dt) failed: " + str(e))
        return None

    # [[key, [temp,2]] , [him,2]]
    def get_dict(data: dict | list | tuple) -> dict | None:
        if isinstance(data, dict):
            return data
        if isinstance(data, (tuple, list)):
            try:
                return {k.lower(): v for k, v in data}
            except:
                logging.info(timenow() + " > Parsed data is not a list of lists: " + str(data))
                return None
        logging.warning(timenow() + " > Payload malformed: " + str(data))
        return None

    try:  # First test if it's a valid json object
        remote_data = json.loads(payload)
    except:  # Else fallback to literal eval
        remote_data = literal_eval(payload)

    remote_data = get_dict(remote_data)
    if remote_data is None:
        return False

    device_key: str
    new_time: str
    dev_data: dict
    # {'pizw/temp': (None, {'Temperature': -99}),
    # 'hydrofor/temphumidpress': (None, {'Temperature': -99, 'Humidity': -99, 'Airpressure': -99})}
    for device_key, (new_time, dev_data) in remote_data.items():
        device_key = device_key.lower()
        location_name = location_name.lower()
        dt_time = validate_time(r_conn, f".{location_name}.{device_key}.time", new_time)
        if dt_time is None:
            continue
        iter_obj = get_dict(dev_data)
        if iter_obj is None:
            continue
        for data_key, value in iter_obj.items():
            if not test_value(data_key, value, 100):
                continue
            set_json(r_conn, f".{location_name}.{device_key}.{data_key}", value)
        else:
            set_json(r_conn, f".{location_name}.{device_key}.time", datetime.now().isoformat("T"))
            set_json(r_conn, f".{location_name}.{device_key}.new", True)
            return True
    return False


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
    return datetime.now().isoformat("T")[:22]


def set_json(r_conn: REJSON_Client, path: str, elem, rootkey="sensors"):
    # I could not think of another solution though :)
    pathkeys = path.split(".")[:0:-1]
    rebuild_path = ""
    if r_conn.get(rootkey, ".") is None:
        r_conn.set(rootkey, ".", {})
    while(i := pathkeys.pop()):
        rebuild_path += "." + i
        if pathkeys and r_conn.get(rootkey, rebuild_path) is None:
            r_conn.set(rootkey, rebuild_path, {})
    r_conn.set(rootkey, rebuild_path, elem)


if __name__ == "__main__":
    main()
