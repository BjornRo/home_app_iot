import gc
import os
import uasyncio  # type:ignore
import ubinascii  # type:ignore
import ujson
import ucryptolib  # type: ignore
from machine import Pin  # type:ignore
from mqtt_async import MQTTClient, config
import network  # type:ignore



PINS = (Pin(0, Pin.OUT, value=0), Pin(2, Pin.OUT, value=0))
MAX_SWITCHES = len(PINS)
SUB = "home/switch/id1/set"
PUB = "home/switch/id1/status"

# For key exchange.
KEY_LEN = 32

# data_bytes.encode() + b'\x00' * ((16 - (len(data_bytes) % 16)) % 16)

with open("config.json", "r") as f:
    cfg_dict = ujson.load(f)

config = {}

config.update(
    dict(
        hostname=cfg_dict["user"],
        ssid=cfg_dict["wifi_ssid"],
        wifi_pw=cfg_dict["wifi_pass"],
        server=cfg_dict["mqtt_broker"],
        client_id=cfg_dict["user"].encode() + b"_unit",
        port=cfg_dict["mqtt_port"],
        user=cfg_dict["user"].encode(),
        password=cfg_dict["pass"].encode(),
    )
)

USR = cfg_dict["user"].encode()
PSW = cfg_dict["pass"].encode()

key = ubinascii.unhexlify(cfg_dict["key"])
DEC = ucryptolib.aes(key, 1)
ENC = ucryptolib.aes(key, 1)
del key
del cfg_dict
gc.collect()

def main():
    _disable_ap()
    loop = uasyncio.get_event_loop()
    loop.run_until_complete(mqtt_connect())
    #loop.create_task(socket_server_sess_key("", 8888, 6))
    loop.run_forever()


async def socket_server_sess_key(host, port, backlog):
    # Server relies on MQTT to run.

    # (1 byte padded_content length) + ((content + padding) % 16 == 0)
    async def _read_msg(dec_key, reader, max_packets=255):
        init = await reader.readexactly(1)
        if not init:
            return None
        init = ord(init)
        if not (0 < init <= max_packets):
            return None
        return dec_key.decrypt(await reader.readexactly(16 * init))

    async def _send_msg(enc_key, writer, msg):
        msg = enc_key.encrypt(msg + b"\x00" * ((16 - (len(msg) % 16)) % 16))
        writer.write((len(msg) // 16).to_bytes(1, "big") + msg)
        await writer.drain()

    async def handler(reader, writer):
        try:
            # Has to use multiple 16 for aes
            # First get session key encrypted with shared aes key.
            enc_sess_key, dec_sess_key = await uasyncio.wait_for(
                key_xchange_login(reader), timeout=4
            )
            if not enc_sess_key:
                return

            while True:
                msg = (await uasyncio.wait_for(_read_msg(dec_sess_key, reader), timeout=60)).lower()
                if not msg:
                    return

                msg = ujson.loads(msg)
                if msg["cmd"] == "status":
                    msg = ujson.dumps({i: p.value() for i, p in enumerate(PINS)}).encode() + b"\r\n"
                    await _send_msg(enc_sess_key, writer, msg)
                elif msg["cmd"] == "set":
                    for i, a in msg["values"].items():
                        if not i.isdigit():
                            return
                        i = int(i)
                        if not (
                            (0 <= i < MAX_SWITCHES) and (a == 0 or a == 1 or isinstance(a, bool))
                        ):
                            return
                        PINS[i].value(int(a))
                    uasyncio.create_task(_publish_mqtt_status())
                    msg = ujson.dumps({i: p.value() for i, p in enumerate(PINS)}).encode() + b"\r\n"
                    await _send_msg(enc_sess_key, writer, msg)
                elif msg["cmd"].startswith("diag"):
                    s = os.statvfs("//")
                    s = s[0] * s[3]
                    F = gc.mem_free()
                    await _send_msg(
                        enc_sess_key,
                        writer,
                        ujson.dumps(
                            {"MB": round(s / 1048576, 3), "use": F / (F + gc.mem_alloc()) * 100}
                        ),
                    )
                elif msg["cmd"].startswith("exit") or msg.startswith("quit"):
                    return
        finally:
            writer.close()
            await writer.wait_closed()
            return

    # Should be run with timeout. Returns session-key decrypter, raises Exception, None.
    async def key_xchange_login(reader):
        # New session key encrypted_shared key. Decrypt and use this new key as session key.
        init = DEC.decrypt(await reader.readexactly(32))
        # Decrypt the key, if the key is invalid after decrypt, login will fail.
        d = ucryptolib.aes(init, 1)

        usr, psw = d.decrypt(await _read_msg(d, reader, 3)).split(b"\r\n", 1)[0].split(b"\n", 1)
        if usr != USR or psw != PSW:
            return None, None

        return ucryptolib.aes(init, 1), d  # Encrypt, Decrypt

    # Start server and await forever
    await uasyncio.socket_server_sess_key(handler, "", 8888, backlog=6)


# region
# MQTT
async def mqtt_connect():
    await mqtt_client.connect()
    await mqtt_client.publish("void", mqtt_client._c["client_id"], qos=1)


async def on_connect():
    await mqtt_client.subscribe(SUB, 1)


async def on_message(_topic, msg, _retained, _qos, _dup):
    if not (8 <= len(msg) <= 8 * MAX_SWITCHES):
        return

    if msg[:1] != b"{":  # If all_off or all_on
        v = 0 if msg[-1:] == b"f" else 1
        for p in PINS:
            p.value(v)
    else:
        try:  # set
            data = ujson.loads(msg)
            for k, v in data.items():
                k = int(k)
                if 0 <= k < MAX_SWITCHES and (v == 0 or v == 1):
                    PINS[k].value(v)
        except:
            return
    uasyncio.create_task(_publish_mqtt_status())


async def _publish_mqtt_status():
    await mqtt_client.publish(PUB, ujson.dumps({i: p.value() for i, p in enumerate(PINS)}), qos=1)


# endregion


def _disable_ap():
    ap_if = network.WLAN(network.AP_IF)
    ap_if.active(False)



if __name__ == "__main__":
    config["subs_cb"] = on_message
    config["connect_coro"] = on_connect
    mqtt_client = MQTTClient(config)
    gc.collect()
    main()
