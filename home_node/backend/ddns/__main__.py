from configparser import ConfigParser
from pathlib import Path
from time import sleep
import netifaces
import requests
import argparse

parser = argparse.ArgumentParser(description='Settings for time delay')
parser.add_argument("time", help="Default seconds")
parser.add_argument("--hour", action="store_true", help="Select hour between")
parser.add_argument("--min", action="store_true", help="Select min between")

args = parser.parse_args()

SLEEP_TIME = 7200


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
    timeout = 10
    cfg = ConfigParser()
    cfg.read(Path(__file__).parent.absolute() / "config.ini")
    url = cfg["DDNS"]["addr"].format(cfg["DDNS"]["domain"], cfg["DDNS"]["token"])
    while 1:
        try:
            for i in netifaces.ifaddresses("wlan0")[netifaces.AF_INET6]:
                if "fe80" == i["addr"][:4]:
                    continue
                requests.get(url + i["addr"], timeout=timeout)
                break
        except:
            pass
        sleep(SLEEP_TIME)


if __name__ == "__main__":
    main()
