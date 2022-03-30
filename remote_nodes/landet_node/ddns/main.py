import argparse
import logging
import netifaces
import os
import requests
from time import sleep

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
    timeout = 15
    sub_addr = os.environ["HOSTNAME"].split(".")[0]
    token =  os.environ["DDNS_TOKEN"]
    url = os.environ["DDNS_ADDR"].format(sub_addr, token)
    while 1:
        try:
            # Update ipv4
            requests.get(url, timeout=timeout)
            sleep(SLEEP_TIME/2)

            # Update ipv6
            for i in netifaces.ifaddresses("wlan0")[netifaces.AF_INET6]:
                if "fe80" == i["addr"][:4]:
                    continue
                requests.get(url + "&ipv6=" + i["addr"], timeout=timeout)
                break
        except requests.exceptions.ConnectTimeout:
            pass
        except Exception as e:
            logging.warning(e)
        sleep(SLEEP_TIME)


if __name__ == "__main__":
    main()
