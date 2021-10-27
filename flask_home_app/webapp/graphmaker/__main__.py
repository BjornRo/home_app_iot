import schedule
import sqlite3
import multiprocessing
from textwrap import dedent

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

DB_FILEPATH = "/db/main_db.db"

DB_QUERY = dedent(
    """\
    SELECT t.time, ktemp, khumid, press, btemp, bhumid, brtemp
    FROM Timestamp t
    LEFT OUTER JOIN
    (SELECT time, temperature AS ktemp
    FROM Temperature
    WHERE measurer = 'kitchen') a ON t.time = a.time
    LEFT OUTER JOIN
    (SELECT time, humidity As khumid
    FROM Humidity
    WHERE measurer = 'kitchen') b ON t.time = b.time
    LEFT OUTER JOIN
    (SELECT time, airpressure AS press
    FROM Airpressure
    WHERE measurer = 'kitchen') c ON t.time = c.time
    LEFT OUTER JOIN
    (SELECT time, temperature AS btemp
    FROM Temperature
    WHERE measurer = 'balcony') d ON t.time = d.time
    LEFT OUTER JOIN
    (SELECT time, humidity As bhumid
    FROM Humidity
    WHERE measurer = 'balcony') e ON t.time = e.time
    LEFT OUTER JOIN
    (SELECT time, temperature AS brtemp
    FROM Temperature
    WHERE measurer = 'bikeroom') f ON t.time = f.time"""
)
data = []

def main():
    while 1:
        schedule.run_pending()
        sleep(10)

# mqtt function does all the heavy lifting sorting out bad data.
def schedule_setup():
    conn = sqlite3.connect(DB_FILEPATH)
    cur = conn.cursor()
    try:
        cur.execute(DB_QUERY)
        data = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    # Process(target=create_graphs_in_new_process, args=(data,)).start()

    # Due to the almost non-existing concurrency, just keep conn alive.
    
    schedule.every().hour.at(":30").do(querydb)
    schedule.every().hour.at(":00").do(querydb)


def matplotlib_setup():
    pass


# def create_graphs_in_new_process(data):
#     col = ("date", "ktemp", "khumid", "pressure", "btemp", "bhumid", "brtemp")
#     df = pd.DataFrame(data, columns=col)
#     df["date"] = pd.to_datetime(df["date"])  # format="%Y-%m-%dT%H:%M" isoformat already
#     plt.plot(df["date"][-48 * 21 :], df["brtemp"][-48 * 21 :])
#     plt.plot(df["date"][-48 * 21 :], df["pressure"][-48 * 21 :] - 1000)
#     plt.show()



if __name__ == "__main__":
    main()
