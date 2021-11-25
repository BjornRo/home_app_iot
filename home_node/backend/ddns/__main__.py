from configparser import ConfigParser
from pathlib import Path
from time import sleep
import netifaces
import requests


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
        sleep(7200)


if __name__ == "__main__":
    main()
