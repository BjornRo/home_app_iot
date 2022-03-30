import argparse
import logging
import os
import requests
import ujson
from datetime import datetime
from pymodules.authsockserver import AuthSocketServer, AuthSockClientHandler
from pymodules.service_layer import blocklist as SL_BL

# Replace json with ujson instead
requests.models.complexjson = ujson  # type:ignore

HOSTNAME = os.environ["HOSTNAME"]
SSLPATH = f"/etc/letsencrypt/live/{HOSTNAME}/"

SERVICE_API = os.environ["SERVICE_API"]

HEADER_LEN = 2
MAX_PAYLOAD_SIZE = 2048


def main():
    name_space = get_arg_namespace()
    sockserv = AuthSocketServer(
        name_space.port,
        HOSTNAME,
        SSLPATH,
        package_handler,
        validate_user=SL_BL.validate_user,
        blocklist_checker=SL_BL.is_banned,
        on_block_ip=SL_BL.block_user,
        header_len=HEADER_LEN,
        max_receive_len=MAX_PAYLOAD_SIZE,
    )
    sockserv.run()


def package_handler(client_handler: AuthSockClientHandler) -> bool:
    recvdata = client_handler.receive()
    if recvdata is None:
        return False

    payload: list | dict = ujson.loads(recvdata)
    if not payload:
        logging.warning(f"Empty/null data sent from: Location: {client_handler.name} | {client_handler.ip}")
        return False

    device_name: str
    data: dict[str, float]
    if isinstance(payload, list):
        device_name, data = payload
    elif isinstance(payload, dict):
        device_name, data = next(iter(payload.items()))
    else:
        return False

    servapi_loc_name = f"{SERVICE_API}/sensors/{client_handler.name.lower()}"
    content = {"time": datetime.utcnow().isoformat(), "data": data}
    if client_handler.session.post(servapi_loc_name + device_name, json=content).status_code < 300:
        return True
    logging.warning(f"Data, was not valid: Location: {client_handler.name} | {device_name}")
    return False


def get_arg_namespace() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--port",
        help="Set port number",
        dest="port",
        action="store",
        required=False,
        type=int,
    )
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
    return args


if __name__ == "__main__":
    main()
