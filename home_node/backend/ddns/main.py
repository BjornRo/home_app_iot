import argparse
import logging
import netifaces
import os
import requests
from time import sleep

# IPV6 only. So progressive!
# This script can run as a cronjob on host-machine but upload and go is worth the potential performance loss.

parser = argparse.ArgumentParser(description="Settings for time delay")
parser.add_argument("device", type=str, help="Device to track, eth0, wlan0 etc...")
parser.add_argument("time", help="Default seconds")
parser.add_argument(
    "--hrs", dest="hour", action="store_true", help="Select hour between", default=False
)
parser.add_argument(
    "--min", dest="minutes", action="store_true", help="Select min between", default=False
)

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
        else:
            SLEEP_TIME = v
        if 60 > SLEEP_TIME:
            SLEEP_TIME = 7200


def main():
    subaddr = os.environ['HOSTNAME'].split(".")[0]
    token = os.environ['DDNS_TOKEN']
    url = os.environ['DDNS_ADDR'].format(subaddr, token)
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
