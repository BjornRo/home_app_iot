import bmemcached
import time

client = bmemcached.Client(("mc1.c1.eu-central-1.ec2.memcachier.com:11211",), "UNAME", "TOKEN")
client2 = bmemcached.Client(("mc3.c1.eu-central-1.ec2.memcachier.com:11211",), "UNAME", "TOKEN")

while 1:
    print(f"Data traveler 1: {client.get('remote_sh')}")
    print(f"Data traveler 2: {client2.get('remote_sh')}")
    time.sleep(10)
