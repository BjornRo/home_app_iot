import time
import gc
import os
import sys


def a():
    s = time.ticks_ms()
    for i in range(5000):
        m = b"a" * 48 + b"\r\n" + (i % 16) * b"\x00"
        d = m[: m.find(b"\r\n")]
        # d = bytearray()
        # for i in range(len(m)-1):
        #     e = m[i].to_bytes(1, "big")
        #     if e == b"\r":
        #         break
        #     d.extend(e)

        d += b"\n"

    print(time.ticks_ms() - s)


def mem_info():
    s = os.statvfs("//")
    s = s[0] * s[3]
    F = gc.mem_free()
    return "{} MB | Use: {:.2f}%".format(s / 1048576, F / (F + gc.mem_alloc()) * 100)


from random import getrandbits
from binascii import hexlify
import hashlib

g = 7
prime = 100000008722222
bits = 256

# Generate Alice's secret and public keys (a,A)
a = getrandbits(bits)
A = pow(g, a, prime)

# Generate Bob's secret and public keys (b,B)
b = getrandbits(bits)
B = pow(g, b, prime)

# Generate the shared secrets
s1 = pow(A, b, prime)
s2 = pow(B, a, prime)


# g=3 p=17 : 3^a % 17, 15
# g=3 p=17 : 3^b % 17, 13

print(len(str(s1)))
print(s1.to_bytes(s1.bit_length() // 8 + 1, byteorder="big"))
s = hashlib.sha256(s1.to_bytes(s1.bit_length() // 8 + 1, byteorder="big"))
k = s.digest()
print("key: ", k)
print("len: ", len(k))

b = bytes.fromhex(
    """      FFFFFFFF FFFFFFFF C90FDAA2 2168C234 C4C6628B 80DC1CD1
      29024E08 8A67CC74 020BBEA6 3B139B22 514A0879 8E3404DD
      EF9519B3 CD3A431B 302B0A6D F25F1437 4FE1356D 6D51C245
      E485B576 625E7EC6 F44C42E9 A637ED6B 0BFF5CB6 F406B7ED
      EE386BFB 5A899FA5 AE9F2411 7C4B1FE6 49286651 ECE45B3D
      C2007CB8 A163BF05 98DA4836 1C55D39A 69163FA8 FD24CF5F
      83655D23 DCA3AD96 1C62F356 208552BB 9ED52907 7096966D
      670C354E 4ABC9804 F1746C08 CA18217C 32905E46 2E36CE3B
      E39E772C 180E8603 9B2783A2 EC07A28F B5C55DF0 6F4C52C9
      DE2BCBF6 95581718 3995497C EA956AE5 15D22618 98FA0510
      15728E5A 8AACAA68 FFFFFFFF FFFFFFFF"""
)

PRIME = 32317006071311007300338913926423828248817941241140239112842009751400741706634354222619689417363569347117901737909704191754605873209195028853758986185622153212175412514901774520270235796078236248884246189477587641105928646099411723245426622522193230540919037680524235519125679715870117001058055877651038861847280257976054903569732561526167081339361799541336476559160368317896729073178384589680639671900977202194168647225871031411336429319536193471636533209717077448227988588565369208645296636077250268955505928362751121174096972998068410554359584866583291642136218231078990999448652468262416972035911852507045361090559


