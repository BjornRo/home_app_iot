import sqlite3
from datetime import datetime
from time import sleep
from pymemcache.client.base import Client
import schedule
import json
import os

# Task every:
task_times = (":30", ":00")

# PATH
DBFILE = "/db/sensor_db.db"
DB_TABLES = "sql_db_tables.sql"


def check_or_create_db() -> None:
    conn = sqlite3.connect(DBFILE)
    cursor = conn.cursor()
    with open(DB_TABLES, "r") as f:
        expr = f.readline()
        tmp_expr = ""
        while(expr):
            tmp_expr += expr.rstrip()
            if tmp_expr and tmp_expr[-1] == ";":
                cursor.execute(tmp_expr[:-1])
                tmp_expr = ""
            expr = f.readline()
    cursor.close()
    conn.close

def main():
    check_or_create_db()

    # Setup memcache and set initial values for memcached.
    class JSerde(object):
        def deserialize(self, _key, value, _flag):
            return json.loads(value)

    memcache_local = Client("memcached:11211", serde=JSerde())

    for t in task_times:
        schedule.every().hour.at(t).do(querydb, args=(memcache_local,))

    while 1:
        schedule.run_pending()
        sleeptime = schedule.idle_seconds()
        if sleeptime is not None and sleeptime > 0:
            sleep(sleeptime)


def querydb(memcache_local: Client):
    time_now = datetime.now().isoformat("T", "minutes")

    # {"sensors": {location: {Device_Name: {measurement: value}}}}
    conn = sqlite3.connect(DBFILE)
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO Timestamp VALUES ('{time_now}')")
    for location in memcache_local.get("sensors"):

        for device, device_data in sub_node_data:
            mkey = device.split("/")[0]
            for table, value in device_data.items():
                cursor.execute(
                    f"INSERT INTO {table} VALUES ('{mkey}', '{time_now}', {value})")
    db.commit()
    cursor.close()


if __name__ == "__main__":
    main()
