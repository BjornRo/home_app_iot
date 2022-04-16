import argparse
import logging
from sys import maxsize
import netifaces
import os
import urllib3
from time import sleep

_default = 3600
parser = argparse.ArgumentParser(description="Settings for time delay")
parser.add_argument("device", type=str, help="Device to track, eth0, wlan0 etc...")
parser.add_argument("time", help="Default seconds", type=int, default=_default)
parser.add_argument("--hrs", dest="hour", action="store_true", help="Select hour between", default=False)
parser.add_argument("--min", dest="minutes", action="store_true", help="Select min between", default=False)

args = parser.parse_args()

if args.hour:
    args.time *= _default
elif args.minutes:
    args.time *= 60
if 60 > args.time:
    args.time = _default

http = urllib3.PoolManager(num_pools=1, maxsize=1, timeout=10)

DOMAIN = os.environ["HOST"].split(".")[0]
TOKEN = os.environ["DDNS_TOKEN"]

while 1:
    try:
        ipv6 = ""
        for i in netifaces.ifaddresses(args.device)[netifaces.AF_INET6]:
            if not i["addr"].startswith("fe80"):
                ipv6 = i["addr"]
                break

        ipv4 = ""
        for i in netifaces.ifaddresses(args.device)[netifaces.AF_INET]:
            if i["addr"].startswith("192.168.1."):
                ipv4 = i["addr"]
                break

        if ipv4 and ipv6:
            http.request("GET", os.environ["DDNS_URL"].format(DOMAIN, TOKEN, ipv4) + ipv6)
    except Exception as e:
        logging.warning(e)
    sleep(args.time)
