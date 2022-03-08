import logging
import os
import requests
import socket
import ssl
import zlib
from contextlib import suppress
from datetime import datetime, timedelta
from threading import Thread


SERVICE_API = os.environ["SERVICE_API"] + "/"
BLOCK_LIST_API = SERVICE_API + "blocklist/"


# SSL Context
HOSTNAME = os.environ['HOSTNAME']
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

# TODO instead of blocking ip in app-layer, maybe add ip firewall.


def main():
    with requests.Session() as session:
        srv = socket.create_server(("", S_PORT), family=socket.AF_INET6, dualstack_ipv6=True)
        socket.setdefaulttimeout(4)  # For ssl handshake and auth.
        srv.listen(8)
        logging.info("Socket server listening on: '{}':{}".format(*srv.getsockname()[:2]))
        with context.wrap_socket(srv, server_side=True) as sslsrv:
            while 1:
                try:
                    client, addr = sslsrv.accept()
                    ip_addr = addr[0]
                    logging.info("Client connected from ip:" + ip_addr)
                    if not _is_banned_blocklist(session, ip_addr):
                        Thread(
                            target=client_handler, args=(session, client, ip_addr), daemon=True
                        ).start()
                    else:
                        _block_user(session, ip_addr)
                        logging.warning("Client is banned: " + ip_addr)
                        with suppress(Exception):
                            client.close()
                except Exception as e:
                    logging.info("Client SSL exception: " + str(e))


def client_handler(session: requests.Session, client: ssl.SSLSocket, ip: str) -> None:
    try:
        location_name, passwd = _recvall(client, ord(_recvall(client, 1))).decode().split("\n")
        valid: bool = session.post(
            SERVICE_API + "auth/verify", json={"username": location_name, "password": passwd}
        ).json()

        if not valid:
            logging.warning(f"Client failed login, [usr: {location_name}, pw: {passwd}]")
            _block_user(session, ip)
            return

        client.settimeout(60)
        client.send(b"OK")

        while 1:
            payload_len = int.from_bytes(_recvall(client, 2, 2), "big")
            if not (0 < payload_len <= MAX_PAYLOAD_SOCKET):
                logging.warning(f"Client tries to send invalid data length: >= {payload_len} bytes")
                break
            recvdata = _recvall(client, payload_len, MAX_PAYLOAD_SOCKET)
            with suppress(zlib.error):
                recvdata = zlib.decompress(recvdata)
            if not _send_to_service_layer(session, location_name, recvdata):
                logging.warning(f"Bad data sent from: {location_name}, {recvdata.decode()[:30]}")
                break
    except socket.timeout as e:
        logging.info(f"Socket timeout, ip: {ip}, {e}")
    except ConnectionAbortedError as e:
        loc = ""
        with suppress(NameError):
            loc = location_name  # type:ignore
        logging.info(f"Socket disconnected, [ip: {ip}, location: {loc}, reason: {e}]")
    except TypeError:
        logging.info("Client sent invalid start header")
    except Exception as e:  # Just to log if any other important exceptions are raised
        logging.warning("Exception from client handler: " + str(e))
    with suppress(Exception):
        client.close()


def _send_to_service_layer(s: requests.Session, location_name: str, json_payload: bytes) -> bool:
    # Payload should already be dumped json-data in bytes form. json.loads loads bytes.
    return s.post(f"{SERVICE_API}sensors/{location_name}", data=json_payload).status_code < 300


def _is_banned_blocklist(s: requests.Session, ip_addr: str) -> bool:
    return s.get(BLOCK_LIST_API + "isbanned/" + ip_addr).json()


def _block_user(session: requests.Session, ip_addr: str) -> None:
    curr_time = datetime.utcnow()

    resp = session.get(BLOCK_LIST_API + ip_addr)
    # If 400, then user hasn't been previously banned. Add new entry.
    if resp.status_code >= 400:
        session.post(
            BLOCK_LIST_API,
            json={
                "ip": ip_addr,
                "ban_expire": (curr_time + timedelta(minutes=BAN_TIME)).isoformat(),
                "manual_ban": False,
            },
        )
    elif resp.status_code == 200:
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
            raise ConnectionAbortedError("recv received zero-byte")
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
