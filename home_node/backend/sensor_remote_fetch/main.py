from redis.commands.json import JSON as REJSON_Client
from datetime import datetime, timedelta
from configparser import ConfigParser
from threading import Thread
from ast import literal_eval
from zlib import decompress
from typing import Optional
from bcrypt import checkpw
import argparse
import sqlite3
import logging
import socket
import redis
import json
import ssl
import os

"""
Blocklist part is under the assumption that summertime/wintertime doesn't exist
which is bogus. But this is not really critical for this kind of project.

For more sensitive data, absolute time that is not affected by Daylight saving is a must for ban time. I.e unix time
"""


# Replace encoder to not use white space. Default to use isoformat for datetime =>
#   Since I know the types I'm dumping. If needed custom encoder or an "actual" default function.
json._default_encoder = json.JSONEncoder(  # type: ignore
    separators=(",", ":"), default=lambda dt: dt.isoformat())

# Config reader -- Path(__file__).parent.absolute() /
CFG = ConfigParser()
CFG.read("config.ini")

# SSL Context
HOSTNAME = CFG["CERT"]["url"]
SSLPATH = f"/sslcerts/live/{HOSTNAME}/"
SSLPATH_TUPLE = (SSLPATH + "fullchain.pem", SSLPATH + "privkey.pem")
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(*SSLPATH_TUPLE)

# Socket info constants.
MAX_PAYLOAD_SOCKET = 2048

# Socket setup
S_PORT = 42661
BAN_TIME = 30  # minutes
ATTEMPT_PENALTY = 5

# MISC
MQTT_HOST = "home.1d"
REJSON_HOST = "rejson"

# DB
DB_FILE = "/db/sensor_rf_blocklist.db"
DB_TABLES = """
CREATE TABLE blocklist (
    ip VARCHAR(46) NOT NULL,
    attempts INT NOT NULL,
    total_attemps INT NOT NULL,
    first_ban_time VARCHAR(26) NOT NULL,
    banned_until VARCHAR(26) NOT NULL,
    comment TEXT NOT NULL,
    PRIMARY KEY (ip)
);
"""


def main() -> None:
    r_conn: REJSON_Client = redis.Redis(host=REJSON_HOST, port=6379, db=int(
        os.getenv("DBSENSOR", "0"))).json()  # type: ignore
    device_credentials = get_default_credentials()
    check_or_create_db()
    socket_handler(device_credentials, r_conn)


def socket_handler(device_cred: dict, r_conn: REJSON_Client) -> None:
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as srv:
        socket.setdefaulttimeout(3)  # For ssl handshake and auth.
        srv.bind(("", S_PORT))
        srv.listen(8)
        with context.wrap_socket(srv, server_side=True) as sslsrv:
            while 1:
                try:
                    # if timeout, client is not connected.
                    client, (c_ip, c_port) = sslsrv.accept()
                    if _is_client_allowed(c_ip, c_port):
                        Thread(target=client_handler, args=(r_conn, device_cred, client), daemon=True).start()
                except Exception as e:  # Don't care about faulty clients with no SSL wrapper.
                    logging.info("Client tried to connect without SSL context: " + str(e))


def client_handler(r_conn: REJSON_Client, device_cred: dict[str, bytes], client: ssl.SSLSocket) -> None:
    try:
        location_name = _validate_user(client, device_cred, _recvall(client, ord(client.recv(1))))
        if location_name is None:
            return _block_user(client.getpeername()[0])

        client.settimeout(60)
        client.send(b"OK")

        while 1:
            payload_len = int.from_bytes(_recvall(client, 3, 3), 'big')
            if not (0 < payload_len <= MAX_PAYLOAD_SOCKET):
                break
            recvdata = _recvall(client, payload_len, MAX_PAYLOAD_SOCKET)
            if not recvdata:
                break
            try:
                recvdata = decompress(recvdata)
            except:  # Test if data is compressed, else it is not -> ignore.
                pass
            if not _parse_and_update(r_conn, location_name, recvdata.decode()):
                break
    except socket.timeout as e:
        logging.info("Socket timeout: " + str(e))
    except Exception as e:  # Just to log if any other important exceptions are raised
        logging.warning("Exception from client handler: " + str(e))
    try:
        client.close()
    except:
        pass


def _is_client_allowed(ip_addr: str, port: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM blocklist WHERE ip = ?", (ip_addr,))
    user = cursor.fetchone()
    if user is not None:
        if user[5] >= datetime.now().isoformat("T"):
            cursor.close()
            conn.close()
            _block_user(ip_addr)
            logging.warning(f"Tmp banned ip tried to connect: {ip_addr}:{port}")
            return False
        elif user[1] >= 1:  # Update: reset attemps.
            usr_data = list(user)
            usr_data[1] = 0
            cursor.execute("INSERT OR REPLACE INTO blocklist VALUES (?,?,?,?,?,?)", usr_data)
            conn.commit()
    cursor.close()
    conn.close()
    return True


def _block_user(ip: str) -> None:
    curr_time = datetime.now()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM blocklist WHERE ip = ?", (ip,))
    user: Optional[tuple] = cursor.fetchone()
    if user is None:
        usr_data = (
            ip,
            1,
            1,
            curr_time.isoformat("T"),
            (curr_time + timedelta(minutes=BAN_TIME)).isoformat("T"),
            "Initial ban"  # Comments are not really useful, we are checking banned_until anyways.
        )
    else:  # {cursor.description[i][0]: user[i] for i in range(len(user))}, if for a future dict-usage.
        usr_data = list(user)
        usr_data[1] += 1  # Increase number of attempts during banned time.
        usr_data[2] += 1  # Total attemps
        if usr_data[1] >= ATTEMPT_PENALTY:
            multiplier = 5
        elif usr_data[1] >= ATTEMPT_PENALTY/2:
            multiplier = 2
        else:
            multiplier = 1
        usr_data[4] = (curr_time + timedelta(minutes=BAN_TIME * usr_data[1] * multiplier)).isoformat("T")
    cursor.execute("INSERT OR REPLACE INTO blocklist VALUES (?,?,?,?,?,?)", usr_data)
    conn.commit()
    cursor.close()
    conn.close()


def _validate_user(client: ssl.SSLSocket, device_cred: dict[str, bytes], data: bytes) -> str | None:
    # dataform: b"login\npassw", data may be None
    # Test if data is somewhat valid. Exactly one \n or else unpack error, which is clearly invalid.
    try:
        location_name, passwd = data.split(b'\n')
        location_name = location_name.decode().lower()
        hash_passwd = device_cred.get(location_name)
        if hash_passwd is None or not location_name:
            raise BaseException
    except:
        # If any data is bad, such as non-existing user or malformed payload, then use a default invalid user.
        location_name = None
        hash_passwd = b'$2b$12$jjWy0CnsCN9Y9Ij4s7eNyeEnmmlJgmJlHANykZnDOA2A3iHYZGZGC'
        passwd = b"hash_is_totally_not_password"
    try:
        if checkpw(passwd, hash_passwd):
            return location_name
    except ValueError | UnicodeDecodeError as e:
        logging.warning("Value-/UnicodeError in validate_user: " + str(e))

    # If validation fails due to invalid user or an active adversary, then log the event.
    c_addr, c_port = client.getpeername()
    logging.warning(f"{c_addr}:{c_port}, tried to connect with data: {str(data)[:24]}...")
    return None


def _parse_and_update(r_conn: REJSON_Client, location_name: str, payload: str) -> bool:
    try:  # First test if it's a valid json object
        remote_data = json.loads(payload)
    except:  # Else fallback to literal eval
        try:
            remote_data = literal_eval(payload)
        except:
            logging.warning("Raw payload malformed: " + str(payload)[:64])
            return False

    remote_data = _get_dict(remote_data)
    if remote_data is None:
        return False

    device_key: str
    new_time: str | None
    dev_data: dict
    # {'pizw': ("2014-12-12T12:44:44.123", {'Temperature': 44.2}),
    # 'hydrofor': (None, {'Temperature': -99, 'Humidity': -99, 'Airpressure': -99})}
    try:
        for device_key, (new_time, dev_data) in remote_data.items():
            if new_time is None:
                continue
            device_key = device_key.split("/")[0].lower()
            if not _validate_time(r_conn, f".{location_name}.{device_key}.time", new_time):
                continue
            iter_obj = _get_dict(dev_data)
            if not iter_obj:
                continue
            data = {}
            # Validate data and update if all values are ok.
            for data_key, value in iter_obj.items():
                if not _test_value(data_key.lower(), value, 100):
                    break
                data[data_key.lower()] = value
            else:
                _set_json(r_conn, f".{location_name}.{device_key}.data", data)
                _set_json(r_conn, f".{location_name}.{device_key}.time", new_time)
                _set_json(r_conn, f".{location_name}.{device_key}.new", True)
        return True
    except:
        logging.warning("Nested data malformed: " + str(remote_data)[:64])
    return False


def _test_value(key: str, value: int | float, magnitude: int = 1) -> bool:
    try:  # Anything that isn't a number will be rejected by try.
        value *= magnitude
        match key:
            case "temperature":
                return -5000 <= value <= 6000
            case "humidity":
                return 0 <= value <= 10000
            case "airpressure":
                return 90000 <= value <= 115000
    except:
        pass
    logging.warning("Bad key/val in data: " + key + " | value: " + str(value))
    return False


def _recvall(client:  ssl.SSLSocket, size: int, buf_size=4096) -> bytes:
    received_chunks = []
    remaining = size
    while remaining > 0:
        received = client.recv(min(remaining, buf_size))
        if not received:
            return b''
        received_chunks.append(received)
        remaining -= len(received)
    return b''.join(received_chunks)


def _validate_time(r_conn: REJSON_Client, r_conn_path: str, new_time: str) -> bool:
    try:
        # Test if timeformat is valid
        datetime.fromisoformat(new_time)
        try:
            # Test if data exists. If not, set a placeholder as time.
            old_time: str = r_conn.get("sensors", r_conn_path)
        except:  # redis.exceptions.ResponseError
            _set_json(r_conn, r_conn_path, datetime.min.isoformat("T"))
            return True
        if old_time < new_time:
            return True
        else:
            logging.info(" > Old data sent: " + new_time)
    except ValueError:
        logging.warning("Invalid timeformat sent: " + str(new_time)[:30])
    return False


# [[temp, 2], [hum, 2]]
def _get_dict(data: dict | list | tuple) -> dict | None:
    if isinstance(data, dict):
        return data
    if isinstance(data, (tuple, list)):
        try:
            return {k: v for k, v in data}
        except:
            pass
    logging.warning("Data payload malformed: " + str(data))
    return None


def _set_json(r_conn: REJSON_Client, path: str, elem, rootkey="sensors") -> None:
    if r_conn.get(rootkey) is None:
        r_conn.set(rootkey, ".", {})

    rebuild_path = ""
    is_root = True
    for p in path.split(".")[1:]:
        tmp = rebuild_path + "." + p
        if r_conn.get(rootkey, "." if is_root else rebuild_path).get(p) is None:
            r_conn.set(rootkey, tmp, {})
        is_root = False
        rebuild_path = tmp
    r_conn.set(rootkey, rebuild_path, elem)


def get_default_credentials() -> dict[str, bytes]:
    return {usr: CFG[usr]["password"].encode() for usr in CFG.sections() if not "cert" == usr.lower()}


def check_or_create_db() -> None:
    # Don't overwrite an existing db-file.
    if os.path.isfile(DB_FILE):
        return

    # Create db file and import tables.
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.executescript(DB_TABLES)
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    # Logging
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        '-v', '--verbose',
        help="Be verbose",
        action="store_const", dest="loglevel", const=logging.INFO,
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)
    main()
