from time import sleep
import logging
import schedule
import requests

# Task every:
TASK_TIMES = (":30", ":00")

SERVICE_API = "http://service_layer_api:8000/sensors"


def main():
    logging.info("Sensor_logger started")

    for t in TASK_TIMES:
        schedule.every().hour.at(t).do(querydb)

    while 1:
        schedule.run_pending()
        sleeptime = schedule.idle_seconds()
        if sleeptime is not None and sleeptime > 0:
            sleep(sleeptime)


def querydb() -> None:
    for _ in range(2):
        resp = requests.get(SERVICE_API + "/data")
        if resp:
            requests.post(SERVICE_API + "/db", json=resp.json())
            return
        sleep(0.1)


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
