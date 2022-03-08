import requests as req
import zlib
import time
import json
import socket
import ssl

SERVICE_API = "http://service_layer_api:8000/"
HOSTNAME = ""

user = "test_user"
passw = "hard_password"

login = (user + "\n" + passw).encode()
data = {"pizw": {"time": "2022-03-08T22:33:53.631231", "data": {"temperature": -2}},"hydrofor": {"time": "2022-03-06T22:43:53.631231", "data": {"temperature": -13}}}
# {"pizw": ["2022-03-06T22:33:53.631231", {"temperature": -99}], "hydrofor": ["2022-03-06T22:33:53.631231", {"temperature": -99, "humidity": -99, "airpressure": -99}]}
# {"pizw": {"time":"2022-03-06T22:33:53.631231", "data":{"temperature": -99}}, "hydrofor": {"time":"2022-03-06T22:33:53.631231", "data":{"temperature": -99, "humidity": -99, "airpressure": -99}}}

context = ssl.create_default_context()#ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
s.connect(("localhost", 42661))
s.settimeout(5)
with context.wrap_socket(s, server_hostname=HOSTNAME) as c:
    c.settimeout(5)
    # Login
    c.send(len(login).to_bytes(1, "big") + login)
    # receive ok
    if c.recv(2) == b"OK":
        payload = zlib.compress(json.dumps(data).encode(), level=9)
        c.sendall(len(payload).to_bytes(2, "big") + payload)
    else:
        print("sadface")

s.close()