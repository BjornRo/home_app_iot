import argparse
import functools
import logging
import os
import ssl
import requests
import ujson
from contextlib import suppress
from paho.mqtt.client import MQTTMessage, Client as MQTTClient
from pymodules.authsockserver import AuthSocketServer, AuthSockClientHandler
from pymodules.datamodels import MQTTPacket
from pymodules.service_layer import blocklist as SL_BL
from time import sleep


"""
Listens to MQTT messages within {THIS_LOCATION}, and announces to each
connected client.

Listens to all clients if there has been a MQTT sent within their network
with the constraint of having their {REMOTE_CONNECTION_NAME} as root of
MQTT-path. Any messages not following this convention is rejected.
This message is then broadcasted to all connected clients.

Clients can connect to the server by sending {n-long byte string representing MSG_LEN}{MSG}.
Logging in by sending credentials: b"login_name\npassword"

Server replises to any message.
Response is b"OK", and b"KO". If b"KO", then server disconnects client.

Messages should follow MQTTPacket-model.
"""

# Replace json with ujson instead
requests.models.complexjson = ujson  # type:ignore

# Addresses
MQTT_HOST = "mqtt.lan"

# TODO check ip
# Socket setup
HOSTNAME = os.environ["HOSTNAME"]

THIS_LOCATION = "home"

HEADER_LEN = 2
MAX_PAYLOAD_SIZE = 2048

SSLPATH = f"/etc/letsencrypt/live/{HOSTNAME}/"

# For storing sockets for annocing new data.
socket_dict: dict[str, ssl.SSLSocket] = {}

retained_msg: dict[str, MQTTPacket] = {}


def on_connect(client: MQTTClient, *_):
    client.subscribe(THIS_LOCATION + "/#")


def on_message(client: MQTTClient, _userdata, msg: MQTTMessage, **kwargs) -> None:
    sockserver: AuthSocketServer = kwargs["sockserver"]
    mqtt_data = MQTTPacket.parse_obj(
        {"topic": msg.topic.lower(), "payload": ujson.loads(msg.payload), "retain": msg.retain}
    )
    if mqtt_data.retain:
        retained_msg[mqtt_data.topic] = mqtt_data
    else:
        if mqtt_data.topic in retained_msg:
            del retained_msg[mqtt_data.topic]
    sockserver.send_to_all(mqtt_data.dict())


def admin_page(client_handler: AuthSockClientHandler, command):
    match command:
        case "status", _:
            status = {
                "this_user:": client_handler.name,
                "connected:": client_handler._sockserv._current_connections,
                "max_connections:": client_handler._sockserv._max_connections,
                "connected users:": list(client_handler._sockserv._authed_client_handlers),
            }
            client_handler.send(status)
        case "send_to_all", v:
            client_handler._sockserv.send_to_all(v, exclude=[])


# What to do when you receive a packet. - Void
def package_handler(client_handler: AuthSockClientHandler, packet: bytes) -> None:
    payload = ujson.loads(packet)
    try:
        mqtt_data = MQTTPacket.parse_obj(payload)
    except:
        if "mqtt_bridge" in client_handler.unused_dict["user_tags"]:
            return admin_page(client_handler, payload)
        return

    if not mqtt_data.topic.startswith(THIS_LOCATION):
        # On message from remote.
        client_handler._kwargs["mqtt"].publish(
            mqtt_data.topic.lower(), ujson.dumps(mqtt_data.payload), retain=mqtt_data.retain
        )
        client_handler._sockserv.send_to_all(mqtt_data.dict(), exclude=[client_handler])


# Send all retained messages within the network to the new connectee.
def on_client_connect(client_handler: AuthSockClientHandler):
    # Get user tags to check for access.
    client_handler.unused_dict["user_tags"] = SL_BL.get_user_tags(client_handler.session, client_handler.name)
    logging.debug(f'User tags: {client_handler.name} | {client_handler.unused_dict["user_tags"]}')

    for mqtt_data in retained_msg.values():
        if mqtt_data.topic.split("/")[0] == client_handler.name:
            continue
        client_handler.send(mqtt_data.dict())


def main():
    name_space = get_arg_namespace()

    logging.info("Mqtt net bridge server: started")
    mqtt = MQTTClient("mqtt_bridge")
    sockserv = AuthSocketServer(
        name_space.port,
        HOSTNAME,
        SSLPATH,
        package_handler,
        on_connect=on_client_connect,
        validate_user=SL_BL.validate_user,
        blocklist_checker=SL_BL.is_banned,
        on_block_ip=SL_BL.block_user,
        header_len=HEADER_LEN,
        max_receive_len=MAX_PAYLOAD_SIZE,
        mqtt=mqtt,
    )

    mqtt.username_pw_set(username=os.environ["NAME"], password=os.environ["PASS"])
    mqtt.on_connect = on_connect
    mqtt.on_message = functools.partial(on_message, sockserver=sockserv)
    while True:
        with suppress(Exception):
            # Wait until mqtt server is connectable. No need to read exceptions here.
            if mqtt.connect(MQTT_HOST, 1883, 60) == 0:
                logging.info("Connected to mqtt!")
                break
        sleep(5)

    # Start
    sockserv.start()
    mqtt.loop_forever()
    logging.warning("Mqtt net bridge server: exited...")


def get_arg_namespace() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--port",
        help="Set port number",
        dest="port",
        action="store",
        required=False,
        default=8888,
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
    # Logging

    main()
