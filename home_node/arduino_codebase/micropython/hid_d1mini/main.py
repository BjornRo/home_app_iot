import asyncio
import network  # type:ignore
import json  # type:ignore
from machine import Pin, UART  # type:ignore
from umqtt.simple import MQTTClient  # type:ignore

with open("cfg.json", "r") as f:
    cfg = json.load(f)

# Pin setup
reader = UART(0, 115200, rx=Pin(4))
writer = UART(1, 115200, tx=Pin(2))


pub_temp = "home/balcony/temphumid"
pub_status = "home/balcony/relay/status"
sub = "home/balcony/relay/command/#"


def main():
    global cfg
    c = MQTTClient(
        client_id=cfg["user"] + "_unit",
        server=cfg["mqtt_host"],
        port=cfg["mqtt_port"],
        user=cfg["user"],
        password=cfg["pass"],
        keepalive=120,
    )
    c.set_callback(on_message)

    connect_mqtt(c)
    while True:
        # Check MQTT
        try:
            c.check_msg()
        except:
            connect_mqtt(c)


def connect_mqtt(c):
    c.connect()
    c.subscribe(sub)
    c.publish(b"void", cfg["user"].encode())


def on_message(_t, msg):
    pass


if __name__ == "__main__":
    print("\n\nStarting module\n")

    a = network.WLAN(network.AP_IF)
    a.active(False)

    w = network.WLAN(network.STA_IF)
    w.active(True)
    w.config(dhcp_hostname="tester_the_one")
    w.connect(cfg["w_ssid"], cfg["w_pass"])
    while not w.isconnected():
        pass

    main()
