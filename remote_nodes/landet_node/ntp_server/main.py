import struct
import socket
from time import time


def s2n():
    t = time() + 2208988800.0
    return (int(t) << 32) + int(abs(t - int(t)) * (1 << 32))


# create socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("", 123))

NTPFORMAT = ">3B b 3I 4Q"
# NTPFORMAT_LEN = struct.calcsize(NTPFORMAT) = 48
while True:
    try:
        data, addr = s.recvfrom(48)
        serverrecv = s2n()

        data = struct.unpack(NTPFORMAT, data)

        version = data[0] >> 3 & 7
        if version <= 4 and data[0] & 7 == 3:
            s.sendto(
                struct.pack(
                    NTPFORMAT,
                    version << 3 | 4,
                    1,
                    0,
                    -29,
                    0,
                    0,
                    0,
                    serverrecv,
                    data[10],
                    serverrecv,
                    s2n(),
                ),
                addr,
            )
    except:
        pass
