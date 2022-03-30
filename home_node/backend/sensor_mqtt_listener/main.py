import logging
import os
import requests
import ujson
from contextlib import suppress
from datetime import datetime
from paho.mqtt.client import MQTTMessage, Client as MQTTClient
from time import sleep

# Addresses
MQTT_HOST = "mqtt.lan"
LOCATION = "home/"
SERVICE_API = os.environ["SERVICE_API"] + "/sensors/" + LOCATION

# MQTT subscription
RELAY_STATUS_PATH = "balcony/relay/status"
SUB_TOPICS = ["bikeroom/temp", "balcony/temphumid", "kitchen/temphumidpress"]

# Replace json with ujson instead
requests.models.complexjson = ujson  # type:ignore
session = requests.Session()


def on_connect(client, *_):
    for topic in SUB_TOPICS + [RELAY_STATUS_PATH]:
        client.subscribe(LOCATION + topic)


def on_message(_client, _userdata, msg: MQTTMessage) -> None:
    topic: str = msg.topic.replace(LOCATION, "")
    data = ujson.loads(msg.payload)

    with suppress(requests.exceptions.ConnectionError):
        # Four statuses of 4 relays (0,1): [0,0,0,1]
        if topic == RELAY_STATUS_PATH and isinstance(data, list):
            if not set(data).difference(set((0, 1))) and len(data) == 4:
                data = [bool(i) for i in data]
                relays = {
                    "light_full": data[0],
                    "light_dim": data[1],
                    "heater": data[2],
                    "unused": data[3],
                }
                session.post(SERVICE_API + topic, json=relays)
            return None

        content = {"time": datetime.utcnow().isoformat(), "data": data}
        session.post(SERVICE_API + topic.split("/")[0], json=content)
        return None


def main():
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    mqtt = MQTTClient("sensor_mqtt_log")
    mqtt.username_pw_set(username=os.environ["NAME"], password=os.environ["PASS"])
    mqtt.on_connect = on_connect
    mqtt.on_message = on_message
    while True:
        with suppress(Exception):
            # Wait until mqtt server is connectable. No need to read exceptions here.
            if mqtt.connect(MQTT_HOST, 1883, 60) == 0:
                logging.info("Connected to mqtt!")
                break
        sleep(5)
    mqtt.loop_forever()
    session.close()


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
