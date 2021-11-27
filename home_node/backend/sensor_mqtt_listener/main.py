from datetime import datetime
from time import sleep
from ast import literal_eval
import redis
from redis.commands.json import JSON as REJSON_Client
import logging
from paho.mqtt.client import Client
import json

# Replace encoder to not use white space. Default to use isoformat for datetime =>
#   Since I know the types I'm dumping. If needed custom encoder or an "actual" default function.
json._default_encoder = json.JSONEncoder(  # type: ignore
    separators=(",", ":"), default=lambda dt: dt.isoformat())

MINOR_KEYS = ("temperature", "humidity", "airpressure")
SUB_TOPICS = ["bikeroom/temp", "balcony/temphumid", "kitchen/temphumidpress"]
RELAY_STATUS_PATH = "balcony/relay/status"

MQTT_HOST = "home.1d"
REJSON_HOST = "rejson"


def main():
    mqtt = Client("sensor_mqtt_log")
    r_conn: REJSON_Client = redis.Redis(host=REJSON_HOST, port=6379, db=0).json()  # type: ignore

    # Create default path
    # {"sensors": {location: {Device_Name: {measurement: value}}}}
    if r_conn.get("sensors") is None:
        r_conn.set("sensors", ".", {})
    for i in SUB_TOPICS:
        r_conn.set("sensors", "." + i.split("/")[0], {})
    r_conn.set("sensors", ".balcony.relay", {})
    r_conn.set("sensors", ".balcony.relay.status", {})

    mqtt_agent(mqtt, r_conn)


def mqtt_agent(mqtt: Client, r_conn: REJSON_Client):
    def on_connect(client, *_):
        client.subscribe("home/" + RELAY_STATUS_PATH)
        for topic in SUB_TOPICS:
            client.subscribe("home/" + topic)

    def on_message(_client, _userdata, msg):
        try:  # Get values into a listlike form - Test valid payload.
            listlike = literal_eval(msg.payload.decode())
            if isinstance(listlike, (tuple, dict, list)):
                pass
            elif isinstance(listlike, (int, float)):
                listlike = (listlike,)
            else:
                logging.warning("Unknown type received")
                return
        except:
            logging.warning("Bad payload received")
            return

        # Handle the topic depending on what it is about.
        topic: str = msg.topic.replace("home/", "")
        if RELAY_STATUS_PATH == topic:  # Test topic. Remove all 0,1. Set should be empty to be valid.
            if not set(listlike).difference(set((0, 1))) and len(listlike) == 4:
                r_conn.set("sensors", ".balcony.relay.status", listlike)
            return
        iter_obj = get_iterable(listlike)
        if iter_obj is None:
            return
        sender = topic.split("/")[0]
        for key, value in iter_obj:
            # If a device sends bad data -> break and discard, else update
            if not _test_value(key, value):
                break
            r_conn.set("sensors", f".{sender}.{key}", value / 100)
        else:
            r_conn.set("sensors", f".{sender}.time", datetime.now().isoformat("T"))
            r_conn.set("sensors", f".{sender}.new", True)

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


def get_iterable(recvdata: dict | list | tuple):
    if isinstance(recvdata, dict) and all([i.lower() in MINOR_KEYS for i in recvdata.keys()]):
        return recvdata.items()
    if isinstance(recvdata, (tuple, list)):
        return zip(MINOR_KEYS, recvdata)
    logging.warning("Payload malformed")
    return None


def _test_value(key: str, value: int | float, magnitude: int = 1) -> bool:
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
        logging.warning("Bad key in data.")
    return False


if __name__ == "__main__":
    main()
