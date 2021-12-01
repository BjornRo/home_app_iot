from redis.commands.json import JSON as REJSON_Client
from paho.mqtt.client import Client
from datetime import datetime
from ast import literal_eval
from time import sleep
import argparse
import logging
import redis
import json

# Replace encoder to not use white space. Default to use isoformat for datetime =>
#   Since I know the types I'm dumping. If needed custom encoder or an "actual" default function.
json._default_encoder = json.JSONEncoder(  # type: ignore
    separators=(",", ":"), default=lambda dt: dt.isoformat())

MINOR_KEYS = ("temperature", "humidity", "airpressure")
SUB_TOPICS = ["bikeroom/temp", "balcony/temphumid", "kitchen/temphumidpress"]
RELAY_STATUS_PATH = "balcony/relay/status"

# Misc
MQTT_HOST = "home.1d"
REJSON_HOST = "rejson"

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

def timenow() -> str:
    return datetime.now().isoformat("T")[:22]


def set_json(r_conn: REJSON_Client, path: str, elem, rootkey="sensors"):
    # I could not think of another solution though :)
    pathkeys = path.split(".")[:0:-1]
    rebuild_path = ""
    if r_conn.get(rootkey, ".") is None:
        r_conn.set(rootkey, ".", {})
    while(i := pathkeys.pop()):
        rebuild_path += "." + i
        if pathkeys and r_conn.get(rootkey, rebuild_path) is None:
            r_conn.set(rootkey, rebuild_path, {})
    r_conn.set(rootkey, rebuild_path, elem)


def main():
    mqtt = Client("sensor_mqtt_log")
    r_conn: REJSON_Client = redis.Redis(host=REJSON_HOST, port=6379, db=0).json()  # type: ignore

    # Create default path if redis cache doesnt exist
    # {"sensors": {location: {Device_Name: {measurement: value}}}}
    for i in SUB_TOPICS:
        set_json(r_conn, ".home." + i.split("/")[0], {})
    set_json(r_conn, ".home.balcony.relay", {})

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
                logging.warning(timenow() + " > Unknown type received")
                return
        except:
            logging.warning(timenow() + " > Bad payload received")
            return

        # Handle the topic depending on what it is about.
        topic: str = msg.topic.replace("home/", "")
        if RELAY_STATUS_PATH == topic:  # Test topic. Remove all 0,1. Set should be empty to be valid.
            if not set(listlike).difference(set((0, 1))) and len(listlike) == 4:
                set_json(r_conn, ".home.balcony.relay.status", listlike)
            return
        iter_obj = get_iterable(listlike)
        if iter_obj is None:
            return
        sender = topic.split("/")[0]
        for key, value in iter_obj:
            # If a device sends bad data -> break and discard, else update
            if not test_value(key, value):
                break
            set_json(r_conn, f".home.{sender}.{key}", value / 100)
        else:
            set_json(r_conn, f".home.{sender}.time", datetime.now().isoformat("T"))
            set_json(r_conn, f".home.{sender}.new", True)

    mqtt.on_connect = on_connect
    mqtt.on_message = on_message
    while True:
        try:  # Wait until mqtt server is connectable. No need to read exceptions here.
            if mqtt.connect(MQTT_HOST, 1883, 60) == 0:
                logging.info(timenow() + " > Connected to mqtt!")
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
    logging.warning(timenow() + " > Payload malformed")
    return None


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
        logging.warning(timenow() + " > Bad key in data.")
    return False


if __name__ == "__main__":
    main()
