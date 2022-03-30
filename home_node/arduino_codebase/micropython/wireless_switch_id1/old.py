import gc
import uasyncio # type:ignore
import ubinascii # type:ignore
import ujson
import ucryptolib  # type: ignore
import socket
from machine import Pin  # type:ignore
from time import sleep
from network import WLAN, AP_IF, STA_IF  # type:ignore

PINS = (Pin(1, Pin.OUT, value=0), Pin(3, Pin.OUT, value=0))
MAX_SWITCHES = len(PINS)


pub = "status"

#data_bytes.encode() + b'\x00' * ((16 - (len(data_bytes) % 16)) % 16)

def main():
    global c, pub
    loc = "home/switch/id1/"
    sub = "set"

    with open("config.json", "r") as f:
        cfg_dict = ujson.load(f)
    connect(cfg_dict["wifi_ssid"], cfg_dict["wifi_pass"], cfg_dict["user"])
    key = ubinascii.unhexlify(cfg_dict["key"])

    config["server"] =  cfg_dict["mqtt_broker"]
    config["port"] =  cfg_dict["mqtt_port"]

    c.set_callback(on_message)
    del cfg_dict

    while c.connect() != 0:
        time.sleep(30)
    c.subscribe(loc + sub)
    pub = loc + pub
    del loc
    del sub
    gc.collect()
    while True:
        c.wait_msg()

async def async_main():
    pass


def on_message(_t, msg):
    if not (8 <= len(msg) <= 8 * MAX_SWITCHES):
        return

    if msg[:1] != b"{":  # If all_off or all_on
        v = 0 if msg[-1:] == b"f" else 1
        for p in PINS:
            p.value(v)
    else:
        try:
            data = ujson.loads(msg)
            for k, v in data.items():
                k = int(k)
                if 0 <= k < MAX_SWITCHES:
                    PINS[k].value(v & 1)  # odd numbers = 1, good enough
        except:
            return
    _publish_mqtt_status()


def _publish_mqtt_status():
    c.publish(pub, ujson.dumps({i: p.value() for i, p in enumerate(PINS)}))





if __name__ == "__main__":
    main()



import micropython
micropython.mem_info(1)
s = os.statvfs("//")
s = s[0] * s[3]
F = gc.mem_free()
print({"MB": round(s / 1048576, 4), "use%": F / (F + gc.mem_alloc()) * 100})
