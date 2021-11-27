import sqlite3
from datetime import datetime
from time import sleep
import redis
from redis.commands.json import JSON as REJSON_Client
import schedule

# Task every:
TASK_TIMES = (":30", ":00")

# PATH
DBFILE = r"db\sensor_db.db"
DB_TABLES = "sql_db_tables.sql"

REJSON_HOST = "rejson"


def check_or_create_db() -> None:
    from os.path import isfile
    if isfile(DB_TABLES):
        return

    # Create db file and import tables
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

    r_conn: REJSON_Client = redis.Redis(host=REJSON_HOST, port=6379, db=0).json()  # type: ignore
    for t in TASK_TIMES:
        schedule.every().hour.at(t).do(querydb, args=(r_conn,))

    while 1:
        schedule.run_pending()
        sleeptime = schedule.idle_seconds()
        if sleeptime is not None and sleeptime > 0:
            sleep(sleeptime)


def querydb(r_conn: REJSON_Client):
    time_now = datetime.now().isoformat("T", "minutes")

    # {"sensors": {location: {Device_Name: {measurement: value}}}}
    conn = sqlite3.connect(DBFILE)
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO Timestamp VALUES ('{time_now}')")
    mc_data = r_conn.get("sensors")  # type:ignore
    if mc_data is None:
        sleep(0.1)  # Try again, else let go.
        mc_data = r_conn.get("sensors")  # type:ignore

    if isinstance(mc_data, dict):
        mc_data: dict[str, dict]
        for location, devices in mc_data.items():
            cursor.execute("SELECT * FROM locations WHERE name == ?", (location,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO locations VALUES (?)", (location, ))
            devices: dict[str, dict]
            for device_name, measurements in devices.items():
                cursor.execute("SELECT * FROM devices WHERE name == ?", (device_name,))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO devices VALUES (?)", (device_name, ))
                measurements: dict[str, int | float | str]
                for measurement_type, value in measurements.items():
                    cursor.execute("SELECT * FROM measureTypes WHERE name == ?", (measurement_type,))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO measureTypes VALUES (?)", (measurement_type, ))
                    cursor.execute("SELECT * FROM deviceMeasures WHERE name == ? AND mtype = ?",
                                   (device_name, measurement_type))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO deviceMeasures VALUES (?,?)", (device_name, measurement_type))
                    cursor.execute("INSERT INTO measurements VALUES (?, ?, ?, ?, ?)",
                                   (location, device_name, measurement_type, time_now, value))
    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
