from datetime import datetime, timedelta
import json
from glob import glob
from configparser import ConfigParser
from bmemcached import Client as mClient
from time import sleep
from textwrap import dedent
from zlib import compress, decompress
import zlib

# from jsonpickle import encode as jpencode
import tarfile
from io import BytesIO
import ssl
import sys

import asyncio
from asyncio_mqtt import Client
from aiosqlite import connect as dbconnect
from aiofiles import open as async_open
from aiohttp import web

# Replace encoder to not use white space. Default to use isoformat for datetime =>
#   Since I know the types I'm dumping. If needed custom encoder or an "actual" default function.
json._default_encoder = json.JSONEncoder(separators=(",", ":"), default=lambda dt: dt.isoformat())

# Ugly imports, premature optimization perhaps. Whatever to make pizw fasterish.

# TODO Dont forget to change connection handshake connecting to home_node
# TODO Split send only device name and omit everything from '/*', pizw/temp -> pizw

# cfg
CFG = ConfigParser()
CFG.read("config.ini")

# Storing queried data, to stop too many IO queries.
QUERY_DELTA_MIN = 30
last_request = [datetime.now()] * 2
last_data = ["null"] * 2

# MISC
OK = 2
COMMAND_LEN = 1
MAIN_ADDR = CFG["MAIN"]["url"]

# File fetching and data requests
DB_COLUMNS = ("time", "htemp", "humid", "press", "ptemp")
DB_QUERY = dedent(
    """\
    SELECT t.time, htemp, humid, press, ptemp
    FROM Timestamp t
    LEFT OUTER JOIN
    (SELECT time, temperature AS htemp
    FROM Temperature
    WHERE measurer = 'hydrofor') a ON t.time = a.time
    LEFT OUTER JOIN
    (SELECT time, humidity As humid
    FROM Humidity
    WHERE measurer = 'hydrofor') b ON t.time = b.time
    LEFT OUTER JOIN
    (SELECT time, airpressure AS press
    FROM Airpressure
    WHERE measurer = 'hydrofor') c ON t.time = c.time
    LEFT OUTER JOIN
    (SELECT time, temperature AS ptemp
    FROM Temperature
    WHERE measurer = 'pizw') d ON t.time = d.time"""
)

DEV_NAME = CFG["DEVICE"]["name"]
BDEV_NAME = DEV_NAME.encode()
DB_FILE = DEV_NAME + ".db"
DB_FILEPATH = "/db/" + DB_FILE

# HTTP Server
H_PORT = 42660

# Socket server
S_PORT = 42661

# Security
TOKEN = CFG["DEVICE"]["token"]
BTOKEN = TOKEN.encode()

# SSL Context
SSLPATH = f'/etc/letsencrypt/live/{CFG["CERT"]["url"]}/'
SSLPATH_TUPLE = (SSLPATH + "fullchain.pem", SSLPATH + "privkey.pem")
context = ssl.SSLContext(ssl.PROTOCOL_TLS)
context.load_cert_chain(*SSLPATH_TUPLE)
stdssl = ssl.SSLContext(ssl.PROTOCOL_TLS)  # ssl.create_default_context()


def main():
    # Defined read only global variables
    # Find the device file to read from.
    file_addr = glob("/sys/bus/w1/devices/28*")[0] + "/w1_slave"
    # To stop subscribing to non-existing devices.
    sub_denylist = ("pizw/temp",)

    while 1:
        # Datastructure is in the form of:
        #  devicename/measurements: for each measurement type: value.
        # New value is a flag to know if value has been updated since last SQL-query. -> Each :00, :30
        tmpdata = {
            "pizw/temp": {"temperature": -99},
            "hydrofor/temphumidpress": {
                "temperature": -99,
                "humidity": -99,
                "airpressure": -99,
            },
        }
        new_values = {key: False for key in tmpdata}  # For DB-query
        last_update = {key: None for key in tmpdata}  # For main node to know when sample was taken.

        # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(reload_ssl())
            loop.create_task(mqtt_agent(sub_denylist, tmpdata, new_values, last_update))
            loop.create_task(read_temp(file_addr, tmpdata, new_values, "pizw/temp", last_update))
            loop.create_task(querydb(tmpdata, new_values))
            loop.create_task(memcache_as(tmpdata, last_update))
            loop.create_task(low_lvl_http((tmpdata, last_update)))
            loop.create_task(socket_server((tmpdata, last_update)))
            loop.create_task(socket_send_data(tmpdata, last_update))
            loop.run_forever()
        except:
            pass
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
            except:
                pass
            finally:
                loop.close()
                sleep(20)
                asyncio.set_event_loop(asyncio.new_event_loop())


async def socket_send_data(tmpdata, last_update):
    async def client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            # Send credentials, login and token.
            login_cred = BDEV_NAME + b"\n" + BTOKEN
            writer.write(len(login_cred).to_bytes(1, "big") + login_cred)
            await writer.drain()
            # If server doesn't reply with ok something has gone wrong. Otherwise just loop until
            # connection fails. Then an exception is thrown and function terminates.
            result = await asyncio.wait_for(reader.readexactly(OK), timeout=5) == b"OK"
            if not result:
                return
            writer.write(b"P")
            await writer.drain()
            result = await asyncio.wait_for(reader.readexactly(OK), timeout=5) == b"OK"
            # TODO change from list to dict: "time": time, "data": data
            while result:
                payload = zlib.compress(
                    json.dumps(
                        {
                            dev.split("/")[0]: [last_update[dev], val]
                            for dev, val in tmpdata.items()
                        }
                    ).encode()
                )
                writer.write(len(payload).to_bytes(3, "big") + payload)
                await writer.drain()
                await asyncio.sleep(10)
        except:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    while 1:
        try:
            task = asyncio.open_connection(MAIN_ADDR, S_PORT, ssl_handshake_timeout=2, ssl=stdssl)
            reader, writer = await asyncio.wait_for(task, timeout=10)
            await client(reader, writer)
        except:
            pass
        # If anything fails, cooldown and try to reconnect.
        await asyncio.sleep(60)


# Simple server to get data with HTTP. Trial to eventually replace memcachier.
async def low_lvl_http(tmpdata_last_update):
    async def handler(request: web.Request):
        try:
            rel_url = str(request.rel_url)[1:].split("/")
            if "status" == rel_url[0] and "get" == rel_url[1]:
                return web.json_response(tmpdata_last_update)
            # Can't decide on query vs sending the file. Just have both ready for usage.
            if TOKEN == rel_url[0]:
                if "query" == rel_url[1]:
                    return web.Response(text=decompress(await get_data_selector("Q")).decode())
                if "file" == rel_url[1]:
                    return web.Response(
                        body=await get_data_selector("F"),
                        content_type="application/octet-stream",
                        headers={"Content-Disposition": f"attachment; filename={DEV_NAME}.tar.gz"},
                    )
        except:
            pass
        return web.Response(status=401)

    runner = web.ServerRunner(web.Server(handler))
    await runner.setup()
    site = web.TCPSite(runner, None, H_PORT, ssl_context=context)
    await site.start()


async def socket_server(tmpdata_last_update):
    async def c_handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            if BTOKEN == await asyncio.wait_for(reader.readexactly(len(BTOKEN)), timeout=4):
                writer.write(b"OK")
                await writer.drain()
                command = await asyncio.wait_for(reader.readexactly(COMMAND_LEN), timeout=4)
                data = None
                if command == b"S":
                    data = compress(jsondumps(tmpdata_last_update).encode())
                elif command == b"Q":
                    data = await get_data_selector("Q")
                elif command == b"F":
                    data = DB_FILE.encode() + b"\n" + await get_data_selector("F")
                if data is not None:
                    writer.write(len(data).to_bytes(3, "big") + data)
                    await writer.drain()
        except:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    srv = await asyncio.start_server(c_handle, None, S_PORT, ssl=context, ssl_handshake_timeout=2)
    async with srv:
        await srv.serve_forever()


async def reload_ssl(seconds=86400):
    while 1:
        await asyncio.sleep(seconds)
        context.load_cert_chain(*SSLPATH_TUPLE)


async def get_data_selector(method_name: str):
    if method_name == "F":
        return await _get_update_data(0, _get_filebytes, DB_FILEPATH, DB_FILE)
    if method_name == "Q":
        return await _get_update_data(1, _get_db_data)
    return None


async def _get_update_data(index, f, *args):
    time_now = datetime.now()
    if last_request[index] < time_now:
        last_request[index] = time_now + timedelta(minutes=QUERY_DELTA_MIN)
        last_data[index] = await f(*args)
    return last_data[index]


# def update_data(index):
#     time_now = datetime.now()
#     if boolean := last_request[index] < time_now:
#         last_request[index] = time_now + timedelta(minutes=QUERY_DELTA_MIN)
#     return boolean


async def _get_db_data():
    async with dbconnect(DB_FILEPATH) as db:
        async with db.execute(DB_QUERY) as c:
            return compress(jsondumps((DB_COLUMNS, await c.fetchall())).encode(), 9)


async def _get_filebytes(filepath, filename):
    async with async_open(filepath, "rb") as f:
        source = BytesIO(await f.read())
    tardb = BytesIO()
    with tarfile.open(fileobj=tardb, mode="w:gz") as tar:
        info = tarfile.TarInfo(filename)
        info.size = source.seek(0, 2)
        source.seek(0)
        tar.addfile(info, source)
    return tardb.getvalue()


async def memcache_as(tmpdata, last_update):
    loop = asyncio.get_event_loop()
    m1 = mClient((CFG["DATA"]["server"],), CFG["DATA"]["user"], CFG["DATA"]["pass"])
    m2 = mClient((CFG["DATA2"]["server"],), CFG["DATA2"]["user"], CFG["DATA2"]["pass"])

    def memcache():
        # Get the data, don't care about race conditions.
        data = jsondumps((tmpdata, last_update, datetime.now()))
        m1.set(DEV_NAME, data)
        m2.set(DEV_NAME, data)

    while 1:
        await asyncio.sleep(10)
        try:
            await loop.run_in_executor(None, memcache)
        except:
            pass


async def mqtt_agent(sub_denylist, tmpdata, new_values, last_update):
    # Since mqtt_agent is async, thus this is sync, no race conditions.
    #  -> Either MQTT or SQL, but not both.
    def on_message(message):
        # Payload is in form of bytes.
        try:
            msg = message.payload
            # Check if string has ( and ) or [ and ]
            if (msg[0] == 40 and msg[-1] == 41) or (msg[0] == 91 and msg[-1] == 93):
                listlike = tuple(int(i) for i in msg[1:-1].split(b","))
            elif msg.isdigit():  # A number.
                listlike = (int(msg),)
            else:  # dict
                # listlike = json.loads(msg) #can't handle json...
                return
            # Handle the topic depending on what it is about.
            topic = message.topic[7:]
            if len(listlike) != len(tmpdata[topic]):
                return

            for key, value in zip(tmpdata[topic], listlike):
                # If a device sends bad data break and don't set flag as newer value.
                if not _test_value(key, value):
                    break
                tmpdata[topic][key] = value / 100
            else:
                new_values[topic] = True
                last_update[topic] = datetime.now().isoformat()
        except:  # Unsupported datastructures or invalid values
            return

    while 1:
        try:
            async with Client("mqtt") as client:
                for topic in tmpdata:
                    if topic not in sub_denylist:
                        await client.subscribe("landet/" + topic)
                async with client.unfiltered_messages() as messages:
                    async for message in messages:
                        on_message(message)
        except:
            pass
        await asyncio.sleep(5)


async def querydb(tmpdata: dict, new_values: dict):
    while 1:
        # Old algo ((1800 - dt.minute * 60 - 1) % 1800) - dt.second + 1

        # Get time to sleep. Expensive algorithm, but queries are few.
        dt = datetime.now()
        # This will always get next 30minutes. If time is 00:00, then 00:30...
        nt = dt.replace(second=0, microsecond=0) + timedelta(minutes=(30 - dt.minute - 1) % 30 + 1)
        await asyncio.sleep((nt - dt).total_seconds())
        # If timer gone too fast and there are seconds left, wait the remaining time, else continue.
        if (remain := (nt - datetime.now()).total_seconds()) > 0:
            print(
                "DB-timer gone too fast", file=sys.stderr
            )  # Maybe too careful. Lets log it and see!
            await asyncio.sleep(remain)
        if not any(new_values.values()):
            continue
        try:
            # Copy values because we don't know how long time the queries will take.
            # Async allows for mutex since we explicit tells it when it's ok to give control to the event loop.
            tmplist = []
            for key, value in new_values.items():
                if value:
                    new_values[key] = False
                    tmplist.append((key, tmpdata[key].copy()))
            # Convert nt to a string. Overwrite the old variable since it won't be used until next loop.
            nt = nt.isoformat("T", "minutes")
            async with dbconnect(DB_FILEPATH) as db:
                await db.execute(f"INSERT INTO Timestamp VALUES ('{nt}')")
                for measurer, data in tmplist:
                    mkey = measurer.partition("/")[0]
                    for tb, val in data.items():
                        await db.execute(f"INSERT INTO {tb} VALUES ('{mkey}', '{nt}', {val})")
                await db.commit()
        except:
            pass


async def read_temp(file_addr: str, tmpdata: dict, new_values: dict, topic: str, last_update: dict):
    while 1:
        found = False
        try:
            async with async_open(file_addr, "r") as f:
                async for line in f:
                    line = line.strip()
                    if not found and line[-3:] == "YES":
                        found = True
                        continue
                    elif found and (eq_pos := line.find("t=")) != -1:
                        if (tmp_val := line[eq_pos + 2 :]).isdigit():
                            conv_val = round(int(tmp_val) / 1000, 1)  # 28785 -> 28.785 -> 28.8
                            if _test_value("Temperature", conv_val, 100):
                                tmpdata[topic]["Temperature"] = conv_val
                                new_values[topic] = True
                                last_update[topic] = datetime.now().isoformat()
                    break
        except:
            pass
        await asyncio.sleep(4)


# Simplified to try catch since we want to compare numbers and not another datatype.
# Less computation for a try/except block than isinstance...
def _test_value(key, value, magnitude=1) -> bool:
    try:
        value *= magnitude
        if key == "Temperature":
            return -5000 <= value <= 6000
        elif key == "Humidity":
            return 0 <= value <= 10000
        elif key == "Airpressure":
            return 90000 <= value <= 115000
    except:
        pass
    return False


if __name__ == "__main__":
    main()
