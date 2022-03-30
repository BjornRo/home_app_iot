import cryptolib  # type: ignore
import gc
import hashlib
import network  # type:ignore
import os
import random
import socket
import time
import ubinascii  # type:ignore
import ujson as json
from machine import Pin  # type:ignore
from umqtt.simple import MQTTClient  # type:ignore


def _hash_enc_pw(str):
    return ubinascii.b2a_base64(hashlib.sha256(str).digest()).decode()


with open("cfg.json", "r") as f:
    cfg = json.load(f)

# Pin setup
PINS = (Pin(0, Pin.OUT, value=0), Pin(2, Pin.OUT, value=0))
MAX_SWITCHES = len(PINS)

# Cryptos
shared_key: bytes = ubinascii.unhexlify(cfg["key"])

SK_DECRYPT = cryptolib.aes(shared_key, 1)
SK_ENCRYPT = cryptolib.aes(shared_key, 1)

prime_bytes = ubinascii.a2b_base64(cfg["prime"])
KEY_BYTES = len(prime_bytes)
PRIME_NUM = int.from_bytes(prime_bytes, "big")
PRIME_MINUS2 = (PRIME_NUM - 2).to_bytes(KEY_BYTES, "big")
GENERATOR = int(cfg["generator"])

# Login
NAME = cfg["user"]

users = {NAME.lower(): {"pw": _hash_enc_pw(cfg["pass"]), "admin": True}}
if "users" in os.listdir():
    with open("users", "r") as f:
        users.update(json.load(f))

# Runtime
pub = b"home/switch/id1/status"
sub = b"home/switch/id1/set"
c = MQTTClient  # placeholder

del cfg["key"], prime_bytes, shared_key
gc.collect()

sockets_state = {}
login_timeout = {}

ADDR = ("0.0.0.0", cfg["port"])
LOGIN_TIMEOUT_TIME = 5000


def _init_socket_server_state():
    for v in sockets_state.values():
        try:
            v["sock"].close()
        except:
            pass
    sockets_state.clear()
    login_timeout.clear()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(ADDR)
    sock.listen(3)
    sock.setblocking(False)
    gc.collect()
    return sock


def main():
    global c, cfg

    c = MQTTClient(
        client_id=cfg["user"] + "_unit",
        server=cfg["mqtt_host"],
        port=cfg["mqtt_port"],
        user=cfg["user"],
        password=cfg["pass"],
        keepalive=1200,
    )
    c.set_callback(on_message)

    c.connect()
    c.subscribe(sub)
    c.publish(b"void", NAME.encode())
    _publish_mqtt_status()

    sock = _init_socket_server_state()

    del cfg
    gc.collect()

    while True:
        # Check MQTT
        try:
            c.check_msg()
        except:
            c.connect()
            c.subscribe(sub)
            c.publish(b"void", NAME.encode())
            _publish_mqtt_status()

        for i, v in login_timeout.items():
            if time.ticks_diff(time.ticks_ms(), v) > LOGIN_TIMEOUT_TIME:  # type:ignore
                try:
                    sockets_state[i]["sock"].close()
                    del sockets_state[i]
                except:
                    pass
                del login_timeout[i]

        # Check socket if someone is connecting
        try:
            # Diffie hellman authenication.
            client, addr = sock.accept()
            sockets_state[id(client)] = {
                "sock": client,
                "name": None,
                "r_remain": 0,
                "s_remain": _send(
                    SK_ENCRYPT,
                    client,
                    json.dumps({"p": PRIME_NUM, "g": GENERATOR, "key_bytes": KEY_BYTES}),
                ),
                "sess_keys": None,
                "ip": str(addr[0]) + ":" + str(addr[1]),
                "buff": [],
            }
            login_timeout[id(client)] = time.ticks_ms()  # type:ignore
        except OSError as e:
            if e.errno == 9:
                sock.close()
                sock = _init_socket_server_state()
                continue

        # Check all clients
        for ident, state in sockets_state.items():
            client = state["sock"]
            try:
                r_remain, s_remain = state["r_remain"], state["s_remain"]
                if s_remain:
                    state["s_remain"] = s_remain[client.send(s_remain) :]

                try:
                    data = client.recv(r_remain if r_remain else 1)
                    if not data:
                        raise ValueError
                except OSError as e:
                    if e.errno == 9:
                        raise RuntimeError
                    continue

                if r_remain:
                    state["buff"].append(data)
                    state["r_remain"] -= len(data)
                    if not state["r_remain"]:
                        # Message complete
                        msg = b"".join(state["buff"])
                        state["buff"].clear()

                        # Initial contact after Server sent DH-info.
                        # Generate key after client sent their X.
                        if state["sess_keys"] is None:
                            msg = _decrypt_remove_pad(SK_DECRYPT, msg)
                            X = int.from_bytes(msg, "big")
                            if X <= 1:
                                return None

                            y = int.from_bytes(
                                bytearray(x & random.getrandbits(8) for x in PRIME_MINUS2), "big"
                            )
                            if y <= 2:
                                y += 2 + random.getrandbits(32)
                            Y = _power(GENERATOR, y, PRIME_NUM)
                            if X == Y:
                                raise ValueError

                            K = hashlib.sha256(_power(X, y, PRIME_NUM).to_bytes(KEY_BYTES, "big")).digest()
                            state["sess_keys"] = (cryptolib.aes(K, 1), cryptolib.aes(K, 1))
                            state["s_remain"] = _send(SK_ENCRYPT, client, Y.to_bytes(KEY_BYTES, "big"))
                            continue

                        # Validate user, and if valid, user has a name, send to handler.
                        msg = _decrypt_remove_pad(state["sess_keys"][1], msg)
                        if state["name"] is None:
                            del login_timeout[id(client)]
                            gc.collect()
                            split_idx = msg.find(b"\n")
                            usr = msg[:split_idx].decode()
                            usr_low = usr.lower()
                            user_info = users.get(usr_low)
                            if user_info:
                                for st in sockets_state.values():
                                    if st["name"] == usr_low:
                                        break
                                else:
                                    if _hash_enc_pw(msg[split_idx + 1 :]) == user_info["pw"]:
                                        state["name"] = usr
                                        _send(state["sess_keys"][0], client, "OK")
                                        continue
                            raise KeyError  # Key doesn't exist, or key is invalid.
                        else:
                            handler(client, state, json.loads(msg))
                else:
                    if state["sess_keys"] is None and ord(data) > KEY_BYTES // 16 + 1:
                        raise ValueError
                    state["r_remain"] = ord(data) * 16
            except:
                client.close()
                del sockets_state[ident]


def _send(enc_key, sock, msg, end=True):
    if isinstance(msg, str):
        msg = msg.encode()
    msg += b"\r\n" + (b"\r\n" if end else b"")
    msg += b"".join((random.getrandbits(8).to_bytes(1, "big") for _ in range((16 - (len(msg) % 16)) % 16)))
    msg = (len(msg) // 16).to_bytes(1, "big") + enc_key.encrypt(msg)
    return msg[sock.send(msg) :]  # Returns remaining send


def handler(client, state, msg):
    is_admin = users[state["name"].lower()]["admin"]

    cmd = msg["cmd"]
    reply = "bad cmd, try help"
    # Casual user access
    if "help" in cmd:
        reply = ["status", "set" + '[values: {"0":1} | "all_on":bool]', "ping", "help"]
        if is_admin:
            reply += [
                "get_users",
                "add_user" + '[values: {"user":"","pass":"","admin":bool}]',
                "del_user" + '[values: "name"]',
                "ls",
                "diag",
            ]
    elif cmd.startswith("exit") or cmd.startswith("quit"):
        return
    elif cmd == "status" or cmd == "set":
        if cmd == "set":
            v = msg["values"].get("all_on")
            if v is not None:
                for i in PINS:
                    i.value(int(v) ^ 1)
            else:
                for i, a in msg["values"].items():
                    i = int(i)
                    a = int(a) ^ 1
                    if (0 <= i < MAX_SWITCHES) and (a == 0 or a == 1):
                        PINS[i].value(a)
            return _publish_mqtt_status()
        reply = json.dumps(_get_all_pins())
    elif cmd == "ping":
        reply = "pong"
    # Admin user access
    elif is_admin:
        if cmd == "diag":
            net = dict(zip(("ip", "submask", "gateway", "dns"), w.ifconfig()))
            net.update(host=w.config("dhcp_hostname") + "s")
            state["s_remain"] = _send(
                state["sess_keys"][0],
                client,
                json.dumps(
                    {
                        "net": net,
                        "ticks_ms": time.ticks_ms(),  # type:ignore
                        "pin_status": _get_all_pins(),
                    }
                )[:-1]
                + ",",
                False,
            )
            del net
            gc.collect()
            free, alloc = gc.mem_free(), gc.mem_alloc()  # type:ignore
            state["s_remain"] += _send(
                state["sess_keys"][0],
                client,
                json.dumps(
                    {
                        "device": NAME,
                        "curr_user": state["name"],
                        "conn_users": [i["name"] for i in sockets_state.values() if i["name"]],
                        "users": users,
                        "mem:": {
                            "used%": alloc / (free + alloc) * 100,
                            "total": free + alloc,
                            "used": alloc,
                            "free": free,
                        },
                    }
                )[1:-1],
                False,
            )
            del alloc, free
            gc.collect()
            s = os.statvfs("//")  # type:ignore
            state["s_remain"] += _send(
                state["sess_keys"][0],
                client,
                ","
                + json.dumps(
                    {
                        "files": os.listdir(),
                        "fs": {
                            "block_siz": s[0] // 8,
                            "total": (s[2] * s[0]) // 8,
                            "used%": ((s[2] - s[3]) / s[2]) * 100,
                            "free": (s[0] * s[3]) // 8,
                            "used": ((s[2] - s[3]) * s[0]) // 8,
                        },
                    }
                )[1:],
            )
            del s
            gc.collect()
            return
        elif cmd == "add_user":
            usr = msg["values"]["user"]
            pw = msg["values"]["pass"]
            admin = msg["values"]["admin"]
            reply = "bad data"
            if users.get(usr.lower()) is None and pw and isinstance(admin, bool):
                users[usr.lower()] = {"pw": _hash_enc_pw(pw), "admin": admin}
                with open("users", "w") as f:
                    json.dump(users, f)
                reply = usr
        elif cmd == "del_user":
            usr = msg["values"]
            reply = "user not exist"
            if usr.lower() in users:
                del users[usr.lower()]
                with open("users", "w") as f:
                    json.dump(users, f)
                reply = usr
        elif cmd == "get_users":
            reply = {u: {k: v for k, v in d.items() if k != "pw"} for u, d in users.items()}
        elif cmd == "ls":
            reply = os.listdir()
    state["s_remain"] = _send(state["sess_keys"][0], client, json.dumps(reply))


def _decrypt_remove_pad(dec, data):
    raw = dec.decrypt(data)
    return raw[: raw.find(b"\r\n\r\n")]


def on_message(_t, msg):
    if not (8 <= len(msg) <= 8 * MAX_SWITCHES):
        return

    if msg[:1] != b"{":  # If all_off or all_on
        msg = msg[-2:-1] if msg[:1] == b'"' else msg[-1:]
        v = 1 if msg == b"f" else 0
        for p in PINS:
            p.value(v)
    else:
        try:  # set
            for k, v in json.loads(msg).items():
                k = int(k)
                if 0 <= k < MAX_SWITCHES and (v == 0 or v == 1):
                    PINS[k].value(v ^ 1)  # inverted... 1 is off
        except:
            pass
    _publish_mqtt_status()


def _get_all_pins() -> dict:
    return {i: _pin_value(i) for i in range(MAX_SWITCHES)}


def _publish_mqtt_status():
    msg = json.dumps(_get_all_pins()).encode()
    for ident, state in sockets_state.items():
        if state["name"]:
            try:
                _send(state["sess_keys"][0], state["sock"], msg)
            except:
                state["sock"].close()
                del sockets_state[ident]
    c.publish(pub, msg, retain=True, qos=1)


def _power(x, y, p):
    res = 1
    x = x % p

    if x == 0:
        return 0

    while y > 0:
        if (y & 1) == 1:
            res = (res * x) % p
        y = y >> 1
        x = (x * x) % p
    return res


def _pin_value(index):
    return PINS[index].value() ^ 1


if __name__ == "__main__":
    for i in PINS:  # turn off
        i.value(1)

    a = network.WLAN(network.AP_IF)
    a.active(False)

    w = network.WLAN(network.STA_IF)
    w.active(True)
    w.config(dhcp_hostname=cfg["user"])
    w.connect(cfg["w_ssid"], cfg["w_pass"])
    while not w.isconnected():
        pass

    print("\n\nStarting module\n")
    del a, cfg["w_ssid"], cfg["w_pass"]
    gc.collect()

    main()
