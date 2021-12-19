import socket
import threading
import queue
from threading import Lock, Thread
from typing import *

HEADER = 64
PORT = 5050
FORMAT = "utf-8"
DISCONNECT_MESSAGE = "!DISCONNECT"
SERVER = "192.168.1.199"  # socket.gethostbyname(socket.gethostname()) #
ADDRESS = (SERVER, PORT)
TIMEOUT = 120
QUEUE_BUFFERT = 20


def socketThread(newClient, pidlock, pidlist):
    client, address = newClient
    print(f"[NEW CONNECTION]> {address} connected.")
    send(client, "OK")
    connected = True
    while connected:
        # Reset timeout
        client.settimeout(TIMEOUT)
        try:
            #TODo checkpoint, ping back to confirm mess length. Also stopping unsynched messages.
            message = client.recv(40).decode(FORMAT)
            print(f"[{address} | msg]> {message}")
            if message == DISCONNECT_MESSAGE:
                # Manual disconnect, otherwise timeout.
                connected = False
            elif message == "EXIT":
                exit()
            send(client, "OK")
        except Exception as e:
            # If timeout triggers, then break out from loop and close the process.
            break
    client.close()
    pid_remove(pidlock, pidlist, threading.currentThread())

def send(client: socket, data: str):
    msg = data.encode(FORMAT)
    #send_len = str(len(message)).encode(FORMAT)
    #send_len += b' ' * (HEADER - len(send_len))
    #threading.Thread(target=client.send(send_len)).start()
    threading.Thread(target=client.send,args=(msg,)).start()


def server_handler():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(ADDRESS)
    server.listen()
    print(f"[SERVER IP]> {SERVER}")

    pidlock = threading.Lock()
    pidlist = []
    call_queue = queue.Queue(QUEUE_BUFFERT)

    # put callers in a queue independant but synchronized to srv thread.
    def callQueue(server, call_queue):
        while True:
            getUser = server.accept()
            call_queue.put(getUser)
    threading.Thread(target=callQueue, args=(server, call_queue), daemon=True).start()
    # Loop -> Wait for queue to fill, then add, spawn and loop.
    while True:
        getUser = call_queue.get()
        pidlock.acquire()
        pidlist = pid_add(pidlock, pidlist, getUser)
        pidlock.release()


def pid_add(pidlock: Lock, pidlist: List, newClient: socket) -> List:
    newpid = threading.Thread(target=socketThread, args=(newClient, pidlock, pidlist))
    newpid.start()
    newpidlist = [newpid] + pidlist
    print(f"[ACTIVE CONNECTIONS]> {len(newpidlist)}")
    return newpidlist;


def pid_remove(pidlock: Lock, pidlist: List, pid: Thread):
    pidlock.acquire()
    if pidlist:
        pidlist = list(filter(lambda ipid: ipid != pid, pidlist))
    print(f"[ACTIVE CONNECTIONS]> {len(pidlist)}")
    #pid.terminate()
    pidlock.release()


def exit():
    sys.exit("[SERVER STOP]")


def init():
    print("[SERVER START]")
    threading.Thread(target=server_handler(), daemon=True).start()


if __name__ == "__main__":
    init()