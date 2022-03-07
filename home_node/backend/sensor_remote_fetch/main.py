from datetime import datetime, timedelta
from configparser import ConfigParser
from threading import Thread
from ast import literal_eval
from contextlib import suppress
from aiohttp import request
import requests
import sqlite3
import logging
import socket
import zlib
import ujson
import ssl
import os


SERVICE_API = "http://service_layer_api:8000/"
BLOCK_LIST_API = SERVICE_API + "blocklist/"


CFG = ConfigParser()
CFG.read("config.ini")


# SSL Context
HOSTNAME = CFG["DEFAULT"]["url"]
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


def main() -> None:
    with requests.Session() as session:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as srv:
            socket.setdefaulttimeout(3)  # For ssl handshake and auth.
            srv.bind(("", S_PORT))
            srv.listen(8)
            with context.wrap_socket(srv, server_side=True) as sslsrv:
                while 1:
                    try:
                        # if timeout, client is not connected.
                        client, (c_ip, c_port) = sslsrv.accept()
                        logging.info("Client connected from ip:" + c_ip)
                        if not _is_banned_blocklist(session, c_ip, c_port):
                            Thread(
                                target=client_handler, args=(session, client), daemon=True
                            ).start()
                        else:
                            logging.warning("Client is banned: " + c_ip)
                    except Exception as e:  # Don't care about faulty clients with no SSL wrapper.
                        logging.info("Client tried to connect without SSL context: " + str(e))


def client_handler(session: requests.Session, client: ssl.SSLSocket) -> None:
    try:
        location_name, passwd = _recvall(client, ord(client.recv(1))).decode().split("\n")

        valid: bool = session.post(
            SERVICE_API + "auth/verify", json={"username": location_name, "password": passwd}
        ).json()

        if not valid:
            return _block_user(session, client.getpeername()[0])

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
            if not _send_to_service_layer(session, location_name, recvdata):
                break
    except socket.timeout as e:
        logging.info("Socket timeout: " + str(e))
    except ValueError as e:
        logging.info(e)
    except Exception as e:  # Just to log if any other important exceptions are raised
        logging.warning("Exception from client handler: " + str(e))
    with suppress(Exception):
        client.close()


# {"pizw": ["2022-03-06T22:33:53.631231", {"temperature": -99}], "hydrofor": ["2022-03-06T22:33:53.631231", {"temperature": -99, "humidity": -99, "airpressure": -99}]}
# {"pizw": {"time":"2022-03-06T22:33:53.631231", "data":{"temperature": -99}}, "hydrofor": {"time":"2022-03-06T22:33:53.631231", "data":{"temperature": -99, "humidity": -99, "airpressure": -99}}}
def _send_to_service_layer(session: requests.Session, location_name: str, payload: bytes) -> bool:
    # Payload should already be dumped json-data in bytes form. json.loads loads bytes.
    if session.post(f"{SERVICE_API}sensors/{location_name}", data=payload).status_code >= 400:
        logging.warning("Bad data sent from: " + location_name + ", " + payload.decode()[:20])
        return False
    else:
        return True


def _is_banned_blocklist(session: requests.Session, ip_addr: str, port: str) -> bool:
    if not session.get(BLOCK_LIST_API + "isbanned" + ip_addr).json():
        return False

    _block_user(session, ip_addr)
    return True


def _block_user(session: requests.Session, ip_addr: str) -> None:
    curr_time = datetime.utcnow()

    resp = session.get(BLOCK_LIST_API + ip_addr)
    # If 400, then user hasn't been previously banned.
    if resp.status_code >= 400:
        session.post(
            BLOCK_LIST_API,
            json={
                "ip": ip_addr,
                "ban_expire": (curr_time + timedelta(minutes=BAN_TIME)).isoformat(),
                "manual_ban": False,
            },
        )
    else:
        # Increases by 1
        attempts: int = session.patch(BLOCK_LIST_API + ip_addr).json()

        if attempts >= ATTEMPT_PENALTY:
            # Reset to "max" attempts so it is not higher than penalty.
            attempts = ATTEMPT_PENALTY - 1
            multiplier = 5
        elif attempts >= ATTEMPT_PENALTY / 2:
            multiplier = 2
        else:
            multiplier = 1
        dt = curr_time + timedelta(minutes=BAN_TIME * attempts * multiplier)
        session.put(
            BLOCK_LIST_API,
            json={"ip": ip_addr, "ban_expire": dt.isoformat(), "attempt_counter": attempts},
        )
    return None


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
