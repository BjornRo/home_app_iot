import logging
import os
import requests
import ujson
from datetime import datetime
from paho.mqtt.client import Client as MQTTClient
from time import sleep

# Addresses
MQTT_HOST = "home.1d"
LOCATION = "home/"
SERVICE_API = os.environ["SERVICE_API"] + "/sensors/" + LOCATION

# MQTT subscription
RELAY_STATUS_PATH = "balcony/relay/status"
SUB_TOPICS = ["bikeroom/temp", "balcony/temphumid", "kitchen/temphumidpress"]

# Raw measured values are multiplied by 100 and converted to int.
MUL_INT_LIST = ["bikeroom/temp", "balcony/temphumid", "kitchen/temphumidpress"]



def main():
    mqtt_agent(MQTTClient("sensor_mqtt_log"))


def mqtt_agent(mqtt: MQTTClient) -> None:
    def on_connect(client, *_):
        for topic in SUB_TOPICS + [RELAY_STATUS_PATH]:
            client.subscribe(LOCATION + topic)

    def on_message(_client, _userdata, msg) -> None:
        topic: str = msg.topic.replace(LOCATION, "")
        # JSON doesn't support paranthesises. "Legacy" from before time.
        data = ujson.loads(msg.payload.replace(b"(", b"[").replace(b")", b"]"))

        # Four statuses of 4 relays (0,1): [0,0,0,1]
        if topic == RELAY_STATUS_PATH:
            _post_data(topic, data)
            return

        # Reduce the value by 100 to get the original values back.
        if topic in MUL_INT_LIST:
            # Convert to iterable due to "legacy". Single values were sent as value only.
            if isinstance(data, int | float):
                data = [data]
            data = [i / 100 for i in data]

        _post_data(topic.split("/")[0], {"time": datetime.utcnow().isoformat(), "data": data})

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


def _post_data(webpath: str, data: dict | list) -> requests.Response:
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
