import socket
import threading
import time

PORT = 5050
UTF8 = "utf-8"
SERVER = "192.168.1.200"
ADDR = (SERVER, PORT)

msg_def = {True: "ON", False: "OFF"}


def _send(reference_id, relay_id: int, minutes: int):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(ADDR)
    client.settimeout(10)
    # print(client.recv(1024).decode(UTF8)) + "\r"
    msg = "RELAY" + str(relay_id) + "_" + "ON" + str(minutes) + "\r"
    #msg = input();
    print("Sending message: " + msg)
    msg = "ALLOFF\r"
    client.send(msg.encode(UTF8))
    print(client.recv(50).decode(UTF8))


def send(*data):
    threading.Thread(target=_send, args=data).start()
    # _send(*data)


class Manager:
    def call(x):
        print(x)


while True:
    send(*[Manager(), 3, 1])
    time.sleep(5)