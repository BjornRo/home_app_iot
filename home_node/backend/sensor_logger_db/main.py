from redis.commands.json import JSON as REJSON_Client
from datetime import datetime
from typing import Optional
from time import sleep
import schedule
import sqlite3
import redis
import os

# Task every:
TASK_TIMES = (":30", ":00")

# DB
DB_FILE = "/db/sensor_db.db"
DB_TABLES = "sql_db_tables.sql"

REJSON_HOST = "rejson"


def check_or_create_db() -> None:
    # Don't overwrite an existing db-file.
    from os.path import isfile
    if isfile(DB_FILE):
        return

    # Create db file and import tables.
    with open(DB_TABLES, "r") as f:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executescript(f.read())
        conn.commit()
        cursor.close()
        conn.close()


def main() -> None:
    check_or_create_db()

    r_conn: REJSON_Client = redis.Redis(host=REJSON_HOST, port=6379, db=int(os.getenv("DBSENSOR","0"))).json()  # type: ignore
    for t in TASK_TIMES:
        schedule.every().hour.at(t).do(querydb, r_conn=r_conn)

    while 1:
        schedule.run_pending()
        sleeptime = schedule.idle_seconds()
        if sleeptime is not None and sleeptime > 0:
            sleep(sleeptime)


def querydb(r_conn: REJSON_Client) -> None:
    time_now = datetime.now().isoformat("T", "seconds")
    cached_data: Optional[dict[str, dict]] = None
    for _ in range(2):  # Two attempts to get the data otherwise ignore.
        cached_data = r_conn.get("sensors")
        if cached_data:
            break
        sleep(0.1)

    # If data is None or empty, or data is not a dict.
    if not cached_data or not isinstance(cached_data, dict):
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO timestamps VALUES (?)", (time_now,))

    # Might have gone overboard with extensibility. It can also be dangerous if an adversary gets access.
    devices: dict[str, dict]
    device_data: dict[str, str | dict]
    for location, devices in cached_data.items():
        # Check if location exist, else add.
        cursor.execute("INSERT OR IGNORE INTO locations VALUES (?)", (location, ))

        for device, device_data in devices.items():
            # If the data is not new then skip.
            if not device_data.get("new"):
                continue
            cursor.execute("INSERT OR IGNORE INTO devices VALUES (?)", (device, ))
            # Set new as false and get the data.
            r_conn.set("sensors", f".{location}.{device}.new", False)
            for measurement_type, value in device_data.get("data").items():  # type:ignore
                cursor.execute("INSERT OR IGNORE INTO measureTypes VALUES (?)", (measurement_type, ))
                cursor.execute("INSERT OR IGNORE INTO deviceMeasures VALUES (?,?)", (device, measurement_type))
                cursor.execute("INSERT OR IGNORE INTO measurements VALUES (?, ?, ?, ?, ?)",
                               (location, device, measurement_type, time_now, value))
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
