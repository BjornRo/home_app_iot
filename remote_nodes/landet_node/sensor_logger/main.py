import asyncio
import logging
import os
import ssl
import ujson
import zlib
from aiofiles import open as async_open
from aiohttp import web
from asyncio_mqtt import Client
from contextlib import suppress
from datetime import datetime, timedelta
from glob import glob
from paho.mqtt.client import MQTTMessage
from pymodules import misc, AsyncAuthSockClient as AASC
from time import sleep

fileargs = misc.get_arg_namespace()

# Polling time for data.
QUERY_DELTA_MIN = 30

# Socket related.
HOME_ADDR = os.environ["HOME_ADDR"]

# Device credentials
NAME = os.environ["NAME"]
PASS = os.environ["PASS"]
LOGIN_CREDENTIALS = NAME.encode() + b"\n" + PASS.encode()

# MQTT
MQTT_SUBS = ["pizw/temp", "hydrofor/temphumidpress"]

# Ports, change in compose file instead.
HTTP_PORT = 42660
SOCK_SERVER_PORT = fileargs.port  # Can be whatever port.

# SSL Context
SSLPATH = f'/etc/letsencrypt/live/{os.environ["HOSTNAME"]}/'
SSLPATH_TUPLE = (SSLPATH + "fullchain.pem", SSLPATH + "privkey.pem")
context = ssl.SSLContext(ssl.PROTOCOL_TLS)
context.load_cert_chain(*SSLPATH_TUPLE)


def main():
    # Find the device file to read from.
    file_addr = glob("/sys/bus/w1/devices/28*")[0] + "/w1_slave"
    while 1:
        # Datastructure is in the form of:
        #  devicename/measurements: for each measurement type: value.
        # New value is a flag to know if value has been updated since last SQL-query. -> Each :00, :30
        tmpdata = {
            "pizw": {"temperature": -99},
            "hydrofor": {
                "temperature": -99,
                "humidity": -99,
                "airpressure": -99,
            },
        }
        new_values = {key: False for key in tmpdata}  # For DB-query
        last_update = {key: None for key in tmpdata}  # For main node to know when sample was taken.

        # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())¨
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with suppress(Exception):
            loop.create_task(low_lvl_http([tmpdata, last_update]))
            loop.create_task(socket_server([tmpdata, last_update]))
            loop.create_task(mqtt_remote_send(tmpdata, new_values, last_update))
            loop.create_task(insert_db_task(tmpdata, new_values))
            loop.create_task(read_temp(file_addr, tmpdata, new_values, "pizw/temp", last_update))
            loop.create_task(reload_ssl())
            loop.run_forever()

        loop.close()
        sleep(20)


# Simple server to get data with HTTP. Trial to eventually replace memcachier.
async def low_lvl_http(tmpdata_last_update):
    async def handler(request: web.BaseRequest):
        with suppress(Exception):
            webpath = [i.lower() for i in request.path[1:].split("/")]
            if "status" == webpath[0]:
                return web.json_response(tmpdata_last_update)
            # Can't decide on query vs sending the file. Just have both ready for usage.
            if len(webpath) >= 3:
                if NAME == webpath[0] and PASS == webpath[1]:
                    match webpath[2]:
                        case "file":
                            return web.Response(
                                body=await misc.get_filebytes(misc.DB_FILE, misc.DB_PATH),
                                content_type="application/octet-stream",
                                headers={
                                    "Content-Disposition": f"attachment; filename={misc.DB_FILE.split('.')[0]}.tar.gz"
                                },
                            )
                return web.Response(status=401)
        return web.Response(status=422)

    runner = web.ServerRunner(web.Server(handler))
    await runner.setup()
    await web.TCPSite(runner, None, HTTP_PORT, ssl_context=context).start()


async def socket_server(full_tmpdata: list):
    async def recv(reader: asyncio.StreamReader) -> str:
        header = int.from_bytes(await asyncio.wait_for(reader.readexactly(3), timeout=4), "big")
        return (await asyncio.wait_for(reader.readexactly(header), timeout=4)).decode()

    async def send(writer: asyncio.StreamWriter, data: bytes, compress=False) -> None:
        if compress:
            data = zlib.compress(data, level=9)
        writer.write(len(data).to_bytes(3, "big") + data)
        await writer.drain()

    async def c_handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        with suppress(Exception):
            if LOGIN_CREDENTIALS.decode() == await recv(reader):
                await send(writer, b"OK")
                match (await recv(reader)).lower():
                    case "status":
                        await send(writer, ujson.dumps(full_tmpdata).encode(), compress=True)
                    case "database":
                        await send(writer, ujson.dumps(await misc.get_db()).encode(), compress=True)
                    case "dbfile":
                        res = await misc.get_filebytes(misc.DB_FILE, misc.DB_PATH)
                        if res is not None:
                            await send(writer, res)
                    case "file":
                        # 4file13database.json
                        filename = await recv(reader)
                        res = await misc.get_filebytes(filename, misc.DB_PATH)
                        if res is not None:
                            await send(writer, res)
                        else:
                            await send(writer, b"KO")
                    case _:
                        await send(writer, b"KO")
        with suppress(Exception):
            writer.close()
            await writer.wait_closed()

    srv = await asyncio.start_server(c_handle, None, SOCK_SERVER_PORT, ssl=context, ssl_handshake_timeout=2)
    async with srv:
        await srv.serve_forever()


async def mqtt_remote_send(tmpdata: dict, new_values: dict, last_update: dict):
    async def on_message(message: MQTTMessage):
        payload: dict[str, float] = ujson.loads(message.payload)
        # Handle the topic depending on what it is about.
        device = message.topic.replace(NAME + "/", "").split("/")[0].lower()

        for key, value in payload.items():
            # If a device sends bad data break and don't set flag as newer value.
            if not misc.test_value(key, value):
                break
            tmpdata[device][key.lower()] = value
        else:
            new_values[device] = True
            last_update[device] = datetime.utcnow().isoformat()
            data = ujson.dumps([device, tmpdata[device]]).encode()
            asyncio.create_task(home.send(data))

    # This client only sends data. MQTT -> Receiver
    home = AASC.AsyncAuthSockClient(HOME_ADDR, fileargs.port, LOGIN_CREDENTIALS, auto_reconnect=True)
    asyncio.create_task(home.connect())

    mqtt_settings = {
        "hostname": "mqtt.lan",
        "client_id": os.environ["MQTT_USER"] + "_unit",
        "username": os.environ["MQTT_USER"],
        "password": os.environ["MQTT_PASS"],
    }
    while 1:
        with suppress(Exception):
            async with Client(**mqtt_settings) as client:
                for topic in MQTT_SUBS:
                    await client.subscribe(NAME + "/" + topic)
                async with client.unfiltered_messages() as messages:
                    async for message in messages:
                        await on_message(message)
        await asyncio.sleep(5)


async def insert_db_task(tmpdata: dict, new_values: dict):
    while 1:
        logging.debug("Inserting data to db...")
        dt = datetime.utcnow()
        # This will always get next 30minutes. If time is 00:00, then 00:30...
        nt = dt.replace(second=0, microsecond=0) + timedelta(minutes=(30 - dt.minute - 1) % 30 + 1)
        await asyncio.sleep((nt - dt).total_seconds())
        # If timer gone too fast and there are seconds left, wait the remaining time, else continue.
        if (remain := (nt - datetime.now()).total_seconds()) > 0:
            logging.warning("DB-timer gone too fast")  # Maybe too careful. Lets log it and see!
            await asyncio.sleep(remain)
        if not any(new_values.values()):
            continue
        with suppress(Exception):
            tmpdict = {}
            for key, value in new_values.items():
                if value:
                    new_values[key] = False
                    tmpdict[key] = tmpdata[key].copy()
            await misc.insert_db({nt.isoformat(timespec="minutes"): tmpdict})


async def read_temp(file_addr: str, tmpdata: dict, new_values: dict, topic: str, last_update: dict):
    while 1:
        found = False
        with suppress(Exception):
            async with async_open(file_addr, "r") as f:
                async for line in f:
                    line = line.strip()
                    if not found and line[-3:].lower() == "yes":
                        found = True
                        continue
                    elif found and (eq_pos := line.find("t=")) != -1:
                        if (tmp_val := line[eq_pos + 2 :]).isdigit():
                            conv_val = float(tmp_val) / 1000  # 28785 -> 28.785
                            if misc.test_value("temperature", conv_val):
                                logging.debug("Temperature read: " + str(conv_val))
                                tmpdata[topic]["temperature"] = conv_val
                                new_values[topic] = True
                                last_update[topic] = datetime.utcnow().isoformat()
                    break
        await asyncio.sleep(4)


async def reload_ssl(seconds=86400):
    while 1:
        await asyncio.sleep(seconds)
        context.load_cert_chain(*SSLPATH_TUPLE)


if __name__ == "__main__":
    main()
