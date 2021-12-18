from redis.commands.json import JSON as REJSON_Client
from datetime import datetime, timedelta
from configparser import ConfigParser
from threading import Thread
from ast import literal_eval
from zlib import decompress
from typing import Optional
from bcrypt import checkpw
import traceback
import argparse
import sqlite3
import logging
import socket
import redis
import json
import ssl

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

##
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


def main() -> None:
    r_conn: REJSON_Client = redis.Redis(host=REJSON_HOST, port=6379, db=0).json()  # type: ignore
    device_credentials = get_default_credentials()
    check_or_create_db()
    socket_handler(device_credentials, r_conn)


def socket_handler(device_cred: dict, r_conn: REJSON_Client) -> None:
    def is_client_allowed(ip_addr: str, port: str) -> bool:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blocklist WHERE ip = ?", (ip_addr,))
        user = cursor.fetchone()
        if user is not None:
            if user[5] >= datetime.now().isoformat("T"):
                cursor.close()
                conn.close()
                block_user(ip_addr)
                logging.warning(f"{timenow()} > Tmp banned ip tried to connect: {ip_addr}:{port}")
                return False
            elif user[1] >= 1:  # Update: reset attemps.
                usr_data = list(user)
                usr_data[1] = 0
                cursor.execute("INSERT OR REPLACE INTO blocklist VALUES (?,?,?,?,?,?)", usr_data)
                conn.commit()
        cursor.close()
        conn.close()
        return True

    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as srv:
        socket.setdefaulttimeout(3)  # For ssl handshake and auth.
        srv.bind(("", S_PORT))
        srv.listen(8)
        with context.wrap_socket(srv, server_side=True) as sslsrv:
            while 1:
                try:
                    # if timeout, client is not connected.
                    client, (c_ip, c_port) = sslsrv.accept()
                    if is_client_allowed(c_ip, c_port):
                        Thread(target=client_handler, args=(r_conn, device_cred, client), daemon=True).start()
                except Exception as e:  # Don't care about faulty clients with no SSL wrapper.
                    logging.info(timenow() + " > Client tried to connect without SSL context: " + str(e))


def client_handler(r_conn: REJSON_Client, device_cred: dict[str, bytes], client: ssl.SSLSocket) -> None:
    def recvall(client:  ssl.SSLSocket, size: int, buf_size=4096) -> bytes:
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
        # dataform: b"login\npassw", data may be None
        # Test if data is somewhat valid. Exactly one \n or else unpack error, which is clearly invalid.
        try:
            location_name, passwd = data.split(b'\n')
            location_name = location_name.decode()
            hash_passwd = device_cred.get(location_name)
            if hash_passwd is None or not location_name:
                raise Exception("User not found")
        except:
            # If any data is bad, such as non-existing user or malformed payload, then use a default invalid user.
            location_name = None
            hash_passwd = b'$2b$12$jjWy0CnsCN9Y9Ij4s7eNyeEnmmlJgmJlHANykZnDOA2A3iHYZGZGC'
            passwd = b"hash_is_totally_not_password"
        try:
            # Each computation takes same time even if invalid user, then side-channel attack should not be viable.
            # Returns the location_name if valid, otherwise returns None.
            if checkpw(passwd, hash_passwd):
                return location_name
        except ValueError as e:
            logging.warning(timenow() + " > ValueError in validate_user: " + str(e))

        # If validation fails due to invalid user or an active adversary, then log the event.
        c_addr, c_port = client.getpeername()
        logging.warning(f"{timenow()} > {c_addr}:{c_port}, tried to connect with data: {str(data)[:24]}...")
        return None

    # No need for contex-manager due to always trying to close conn at the end.
    try:  # First byte msg len => read rest of msg => parse and validate.
        location_name = validate_user(device_cred, recvall(client, ord(client.recv(1))))
        if location_name is None:
            return block_user(client.getpeername()[0])
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
    except Exception as e:  # Just to log if any other important exceptions are raised
        logging.warning(timenow() + " > Exception from client handler: " + str(e))
    try:
        client.close()
    except:
        pass


def block_user(ip: str) -> None:
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
        except ValueError as e:
            logging.info(timenow() + " > Time conversion (str -> dt) failed: " + str(e))
        except Exception as e:
            logging.info(timenow() + " > Time validation failed: " + str(e))
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
        data = {}
        for data_key, value in iter_obj.items():
            if not test_value(data_key, value, 100):
                continue
            data[data_key] = value
        else:
            set_json(r_conn, f".{location_name}.{device_key}.data", data)
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
        logging.warning(timenow() + " > Bad key in data: " + key + " | value: " + str(value))
    return False


def get_default_credentials() -> dict[str, bytes]:
    return {usr: CFG[usr]["password"].encode() for usr in CFG.sections() if not "cert" == usr.lower()}


def timenow() -> str:
    return datetime.now().isoformat("T")[:22]


def set_json(r_conn: REJSON_Client, path: str, elem, rootkey="sensors") -> None:
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


def check_or_create_db() -> None:
    # Don't overwrite an existing db-file.
    from os.path import isfile
    if isfile(DB_FILE):
        return

    # Create db file and import tables.
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.executescript(DB_TABLES)
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
