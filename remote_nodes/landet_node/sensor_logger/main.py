import aiocron
import aiosqlite
import asyncio
import os
import ssl
import sqlite3
import ujson as json
from aiofiles import open as async_open
from aiohttp import web
from asyncio_mqtt import Client as MQTTClient, ProtocolVersion
from contextlib import suppress
from datetime import datetime, timezone
from glob import glob
from paho.mqtt.client import MQTTMessage
from pymodules import misc
from typing import Any

tz = timezone.utc
timenow = lambda: datetime.utcnow().isoformat(timespec="minutes")

# Device credentials
location_name = os.environ["NAME"]
mqtt_name = os.environ["MQTT_USER"]
passw = os.environ["HTTP_PW"]

# DB
db_path = "/appdata/"
db_file = os.environ["NAME"] + ".db"
db_filepath = db_path + db_file

# MQTT
mqtt_subs = ["hydrofor/sensor/data"]
mqtt_pub = f"{location_name}/{mqtt_name}/sensor/data"

http_port = 42660

# SSL Context
ssl_path = f'/etc/letsencrypt/live/{os.environ["HOST"]}/'
ssl_path_tuple = (ssl_path + "fullchain.pem", ssl_path + "privkey.pem")
context = ssl.SSLContext(ssl.PROTOCOL_TLS)
context.load_cert_chain(*ssl_path_tuple)

mqtt_client: None | MQTTClient = None


def main():
    global loop
    if not os.path.isfile(db_filepath):
        db = sqlite3.connect(db_filepath)
        db.execute("CREATE TABLE snapshots (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.commit()
        db.close()
        del db

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while 1:
        tmpdata = {
            mqtt_name: {"temperature": -99, "time": datetime.min, "new": False},
            "hydrofor": {
                "temperature": -99,
                "humidity": -99,
                "airpressure": -99,
                "time": datetime.min,
                "new": False,
            },
        }

        with suppress(Exception):
            loop.create_task(low_lvl_http(tmpdata))
            loop.create_task(mqtt_listener(tmpdata))
            loop.run_forever()
        loop.close()

        from time import sleep

        sleep(20)


async def low_lvl_http(tmpdata):
    async def handler(request: web.BaseRequest):
        with suppress(Exception):
            webpath = [i.lower() for i in request.path[1:].split("/")]
            if "status" == webpath[0]:
                return web.json_response(tmpdata)
            if len(webpath) >= 3:
                if mqtt_name == webpath[0] and passw == webpath[1]:
                    match webpath[2].lower():
                        case "file":
                            return web.Response(
                                body=await misc.get_filebytes(db_file, db_path),
                                content_type="application/octet-stream",
                                headers={
                                    "Content-Disposition": f"attachment; filename={db_file.split('.')[0]}.tar.gz"
                                },
                            )
                return web.Response(status=401)
        return web.Response(status=422)

    runner = web.ServerRunner(web.Server(handler))
    await runner.setup()
    await web.TCPSite(runner, None, http_port, ssl_context=context).start()


async def mqtt_listener(tmpdata: dict):
    global mqtt_client

    async def on_message(message: MQTTMessage):
        payload: dict[str, float] = json.loads(message.payload)

        device = message.topic.split("/")[1]

        for key, value in payload.items():
            if not misc.test_value(key, value):
                break
            tmpdata[device][key] = value
        else:
            tmpdata[device]["new"] = True
            tmpdata[device]["time"] = datetime.utcnow()

    mqtt_settings = {
        "hostname": os.environ["HOST"],
        "port": 8883,
        "client_id": os.environ["MQTT_USER"] + "_unit",
        "username": os.environ["MQTT_USER"],
        "password": os.environ["MQTT_PASS"],
        "tls_context": ssl.create_default_context(),
        "protocol": ProtocolVersion.V31,
    }
    while 1:
        with suppress(Exception):
            async with MQTTClient(**mqtt_settings) as client:
                mqtt_client = client
                for topic in mqtt_subs:
                    await client.subscribe(f"{location_name}/{topic}")
                await client.publish("void", mqtt_name)
                async with client.unfiltered_messages() as messages:
                    async for message in messages:
                        await on_message(message)
        mqtt_client = None
        await asyncio.sleep(5)


@aiocron.crontab("*/30 * * * *", tz=tz)
async def insert_db_task(tmpdata: dict[str, dict[str, Any]]):
    with suppress(Exception):
        new_data = []
        for device_name, data_dict in tmpdata.items():
            item = data_dict.copy()
            data_dict["new"] = False
            if item.pop("new"):
                del item["time"]
                new_data.append({"location": location_name, "name": device_name, **item})

        async with aiosqlite.connect(db_filepath) as db:
            await db.execute(
                "INSERT INTO snapshots VALUES (?, ?)",
                (timenow(), json.dumps(new_data)),
            )
            await db.commit()


@aiocron.crontab("* * * * * */5", tz=tz)
async def read_temp(tmpdata: dict):
    file_addr = glob("/sys/bus/w1/devices/28*")[0] + "/w1_slave"
    found = False
    with suppress(Exception):
        async with async_open(file_addr, "r") as f:
            async for line in f:
                line = line.strip()
                if not found and line[-3:].lower() == "yes":
                    found = True
                    continue
                elif found and (eq_pos := line.find("t=")) != -1:
                    if not (tmp_val := line[eq_pos + 2 :]).isdigit():
                        return

                    val = float(tmp_val) / 1000  # 28785 -> 28.785
                    if not misc.test_value("temperature", val):
                        return

                    tmpdata[mqtt_name]["temperature"] = val
                    tmpdata[mqtt_name]["new"] = True
                    tmpdata[mqtt_name]["time"] = datetime.utcnow()
                    if mqtt_client is None:
                        return
                    await mqtt_client.publish(mqtt_pub, json.dumps({"temperature": val}), qos=1)


@aiocron.crontab("0 0 * * *", tz=tz)
async def reload_ssl():
    context.load_cert_chain(*ssl_path_tuple)


if __name__ == "__main__":
    main()
