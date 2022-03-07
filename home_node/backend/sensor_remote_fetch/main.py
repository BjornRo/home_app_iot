from datetime import datetime, timedelta
from configparser import ConfigParser
from threading import Thread
from ast import literal_eval
from bcrypt import checkpw
from contextlib import suppress
import requests
import sqlite3
import logging
import socket
import zlib
import ujson
import ssl
import os

"""
Blocklist part is under the assumption that summertime/wintertime doesn't exist
which is bogus. But this is not really critical for this kind of project.

For more sensitive data, absolute time that is not affected by Daylight saving is a must for ban time. I.e unix time
"""

SERVICE_API = "http://service_layer_api:8000/sensors/"


# Replace encoder to not use white space. Default to use isoformat for datetime =>
#   Since I know the types I'm dumping. If needed custom encoder or an "actual" default function.
json._default_encoder = json.JSONEncoder(  # type: ignore
    separators=(",", ":"), default=lambda dt: dt.isoformat()
)

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
    device_credentials = get_default_credentials()
    check_or_create_db()
    socket_handler(device_credentials)


def socket_handler(device_cred: dict) -> None:
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
                        Thread(
                            target=client_handler, args=(device_cred, client), daemon=True
                        ).start()
                except Exception as e:  # Don't care about faulty clients with no SSL wrapper.
                    logging.info("Client tried to connect without SSL context: " + str(e))


def client_handler(device_cred: dict[str, bytes], client: ssl.SSLSocket) -> None:
    try:
        location_name = _validate_user(client, device_cred, _recvall(client, ord(client.recv(1))))
        if location_name is None:
            return _block_user(client.getpeername()[0])

        client.settimeout(60)
        client.send(b"OK")

        while 1:
            payload_len = int.from_bytes(_recvall(client, 3, 3), "big")
            if not (0 < payload_len <= MAX_PAYLOAD_SOCKET):
                break
            recvdata = _recvall(client, payload_len, MAX_PAYLOAD_SOCKET)
            if not recvdata:
                break
            with suppress(zlib.error):
                recvdata = zlib.decompress(recvdata)
            if not _send_to_service_layer(location_name, recvdata):
                break
    except socket.timeout as e:
        logging.info("Socket timeout: " + str(e))
    except Exception as e:  # Just to log if any other important exceptions are raised
        logging.warning("Exception from client handler: " + str(e))
    with suppress(Exception):
        client.close()


def _is_client_allowed(ip_addr: str, port: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM blocklist WHERE ip = ?", (ip_addr,))
    user = cursor.fetchone()
    if user is not None:
        if user[5] >= datetime.utcnow().isoformat("T"):
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
    curr_time = datetime.utcnow()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM blocklist WHERE ip = ?", (ip,))
    user: tuple | None = cursor.fetchone()
    if user is None:
        usr_data = (
            ip,
            1,
            1,
            curr_time.isoformat("T"),
            (curr_time + timedelta(minutes=BAN_TIME)).isoformat("T"),
            "Initial ban",  # Comments are not really useful, we are checking banned_until anyways.
        )
    else:  # {cursor.description[i][0]: user[i] for i in range(len(user))}, if for a future dict-usage.
        usr_data = list(user)
        usr_data[1] += 1  # Increase number of attempts during banned time.
        usr_data[2] += 1  # Total attemps
        if usr_data[1] >= ATTEMPT_PENALTY:
            multiplier = 5
        elif usr_data[1] >= ATTEMPT_PENALTY / 2:
            multiplier = 2
        else:
            multiplier = 1
        usr_data[4] = (
            curr_time + timedelta(minutes=BAN_TIME * usr_data[1] * multiplier)
        ).isoformat("T")
    cursor.execute("INSERT OR REPLACE INTO blocklist VALUES (?,?,?,?,?,?)", usr_data)
    conn.commit()
    cursor.close()
    conn.close()


def _validate_user(client: ssl.SSLSocket, device_cred: dict[str, bytes], data: bytes) -> str | None:
    # dataform: b"login\npassw", data may be None
    # Test if data is somewhat valid. Exactly one \n or else unpack error, which is clearly invalid.
    try:
        location_name, passwd = data.split(b"\n")
        location_name = location_name.decode().lower()
        hash_passwd = device_cred.get(location_name)
        if hash_passwd is None or not location_name:
            raise BaseException
    except:
        # If any data is bad, such as non-existing user or malformed payload, then use a default invalid user.
        location_name = None
        hash_passwd = b"$2b$12$jjWy0CnsCN9Y9Ij4s7eNyeEnmmlJgmJlHANykZnDOA2A3iHYZGZGC"
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


# {"pizw": ["2022-03-06T22:33:53.631231", {"temperature": -99}], "hydrofor": ["2022-03-06T22:33:53.631231", {"temperature": -99, "humidity": -99, "airpressure": -99}]}
# {"pizw": {"time":"2022-03-06T22:33:53.631231", "data":{"temperature": -99}}, "hydrofor": {"time":"2022-03-06T22:33:53.631231", "data":{"temperature": -99, "humidity": -99, "airpressure": -99}}}
def _send_to_service_layer(location_name: str, payload: bytes) -> bool:
    # Payload should already be dumped json-data in bytes form. json.loads loads bytes.
    if requests.post(SERVICE_API + location_name, data=payload).status_code >= 400:
        logging.warning("Bad data sent from: " + location_name + ", " + payload.decode()[:20])
        return False
    else:
        return True


def _recvall(client: ssl.SSLSocket, size: int, buf_size=4096) -> bytes:
    received_chunks = []
    remaining = size
    while remaining > 0:
        received = client.recv(min(remaining, buf_size))
        if not received:
            return b""
        received_chunks.append(received)
        remaining -= len(received)
    return b"".join(received_chunks)


def get_default_credentials() -> dict[str, bytes]:
    return {
        usr: CFG[usr]["password"].encode() for usr in CFG.sections() if not "cert" == usr.lower()
    }


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
        "-d",
        "--debug",
        help="Print lots of debugging statements",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Be verbose",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)
    main()
