from ast import literal_eval
from datetime import datetime
from paho.mqtt.client import Client
from time import sleep
import json
import logging
import requests


RELAY_STATUS_PATH = "balcony/relay/status"
SUB_TOPICS = ["bikeroom/temp", "balcony/temphumid", "kitchen/temphumidpress", RELAY_STATUS_PATH]

# Misc
MQTT_HOST = "home.1d"
SERVICE_API = "http://service_layer_api:8000/sensors/home/"


def main():
    mqtt = Client("sensor_mqtt_log")

    mqtt_agent(mqtt)


def mqtt_agent(mqtt: Client) -> None:
    def on_connect(client, *_):
        for topic in SUB_TOPICS:
            client.subscribe("home/" + topic)

    def on_message(_client, _userdata, msg) -> None:
        topic: str = msg.topic.replace("home/", "")
        try:
            try:
                data = json.loads(msg.payload)
            except:
                data = literal_eval(msg.payload.decode())

            if topic == RELAY_STATUS_PATH:
                _post_data(topic, data)
            else:
                _post_data(topic.split("/")[0], {"time": datetime.utcnow().isoformat(), "data": data})
        except:
            logging.warning(f'Bad data from: {topic.split("/")[0]}, data: {str(msg.payload)[:26]}')

    mqtt.on_connect = on_connect
    mqtt.on_message = on_message
    while True:
        try:  # Wait until mqtt server is connectable. No need to read exceptions here.
            if mqtt.connect(MQTT_HOST, 1883, 60) == 0:
                logging.info("Connected to mqtt!")
                break
        except:
            pass
        sleep(5)
    mqtt.loop_forever()


def _post_data(webpath: str, data: dict | str | list | tuple) -> requests.Response:
    return requests.post(SERVICE_API + webpath, json=data)


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
