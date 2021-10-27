from ast import literal_eval
import paho.mqtt.client as mqtt
from datetime import datetime
import sqlite3
from threading import Thread
import schedule
import time
from pymemcache.client.base import Client
import json

# Setup and run. Scheduler queries database every full or half hour. Mqtt queries tempdata to memory.
def main():
    tmpdata = {
        "bikeroom/temp": {"Temperature": None},
        "balcony/temphumid": {"Temperature": None, "Humidity": None},
        "kitchen/temphumidpress": {"Temperature": None, "Humidity": None, "Airpressure": None},
    }

    Thread(target=mqtt_agent, args=(tmpdata,), daemon=True).start()
    schedule_setup(tmpdata)

    # Poll tmpdata until all Nones are gone.
    while True:
        time.sleep(1)
        for value_list in tmpdata.values():
            if None in value_list.values():
                break
        else:
            break

    while True:
        schedule.run_pending()
        time.sleep(10)


# mqtt function does all the heavy lifting sorting out bad data.
def schedule_setup(tmpdata: dict):
    def querydb():
        time_now = datetime.now().isoformat("T", "minutes")
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO Timestamp VALUES ('{time_now}')")
        for location in tmpdata.keys():
            measurer = location.split("/")[0]
            for table, value in tmpdata[location].items():
                cursor.execute(f"INSERT INTO {table} VALUES ('{measurer}', '{time_now}', {value})")
        db.commit()
        cursor.close()

    db = sqlite3.connect("/var/www/database.db")
    schedule.every().hour.at(":30").do(querydb)
    schedule.every().hour.at(":00").do(querydb)


def mqtt_agent(tmpdata: dict, status_path=["balcony/relay/status"]):
    def on_connect(client, *_):
        for topic in list(tmpdata.keys()) + status_path:
            client.subscribe("home/" + topic)

    def on_message(client, userdata, msg):
        topic = msg.topic.replace("home/", "")
        # Test if data is a listlike or a value.
        try:
            listlike = literal_eval(msg.payload.decode("utf-8"))
            if isinstance(listlike, dict):
                listlike = tuple(listlike.values())
            elif not (isinstance(listlike, tuple) or isinstance(listlike, list)):
                listlike = (listlike,)
        except:
            return
        if status_path[0] in topic:
            if not set(listlike).difference(set((0, 1))) and len(listlike) == 4:
                memcache.set("relay_status", listlike)
            return
        if len(listlike) != len(tmpdata[topic]):
            return
        for key, value in zip(tmpdata[topic].keys(), listlike):
            if not isinstance(value, int):
                continue
            if key == "Temperature" and not -2500 <= value <= 5000:
                continue
            elif key == "Humidity" and not 0 <= value <= 10000:
                continue
            elif key == "Airpressure" and not 90000 <= value <= 115000:
                continue
            tmpdata[topic][key] = value / 100
        memcache.set("weather_data_home", tmpdata)

    # setup memcache
    class JSerde(object):
        def serialize(self, key, value):
            if isinstance(value, str):
                return value, 1
            return json.dumps(value), 2

    memcache = Client("/var/run/memcached/memcached.sock", serde=JSerde())

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("www.home", 1883, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
