from configparser import ConfigParser
from pathlib import Path
from time import sleep
import netifaces
import requests


def main():
    timeout = 15
    cfg = ConfigParser()
    cfg.read(Path(__file__).parent.absolute() / "config.ini")
    url = cfg["DDNS"]["addr"].format(cfg["DDNS"]["domain"], cfg["DDNS"]["token"])
    while 1:
        try:
            # Update ipv4
            requests.get(url, timeout=timeout)
            sleep(1200)

            # Update ipv6
            for i in netifaces.ifaddresses("wlan0")[netifaces.AF_INET6]:
                if "fe80" == i['addr'][:4]:
                    continue
                requests.get(url + "&ipv6=" + i['addr'], timeout=timeout)
                break
        except:
            pass
        sleep(6000)


if __name__ == "__main__":
    main()
