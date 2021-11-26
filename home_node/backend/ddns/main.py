from configparser import ConfigParser
from pathlib import Path
from time import sleep
import netifaces
import requests
import logging
import argparse

parser = argparse.ArgumentParser(description='Settings for time delay')
parser.add_argument("device", type=str, help="Device to track, eth0, wlan0 etc...")
parser.add_argument("time", help="Default seconds")
parser.add_argument("--hrs", action="store_true", help="Select hour between")
parser.add_argument("--min", action="store_true", help="Select min between")

args = parser.parse_args()

SLEEP_TIME = 7200
CONTACT_TIMEOUT = 10  # Seconds


if args.time:
    v = float(args.time)
    if 0 < v:
        if args.hour:
            SLEEP_TIME = v * 3600
        elif args.minutes:
            SLEEP_TIME = v * 60
        if 60 < SLEEP_TIME:
            SLEEP_TIME = 7200


def main():
    cfg = ConfigParser()
    cfg.read(Path(__file__).parent.absolute() / "config.ini")
    url = cfg["DDNS"]["addr"].format(cfg["DDNS"]["domain"], cfg["DDNS"]["token"])
    while 1:
        try:
            for i in netifaces.ifaddresses(args.device)[netifaces.AF_INET6]:
                if "fe80" == i["addr"][:4]:
                    continue
                requests.get(url + i["addr"], timeout=CONTACT_TIMEOUT)
                break
        except requests.exceptions.ConnectTimeout:
            pass
        except Exception as e:
            logging.warning(e)
        sleep(SLEEP_TIME)


if __name__ == "__main__":
    main()
