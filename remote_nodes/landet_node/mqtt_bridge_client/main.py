import asyncio
import os
import ssl
import ujson as json
from pymodules import datamodels as m, misc, AsyncAuthSockClient as AASC
from asyncio_mqtt import Client as MQTTClient, ProtocolVersion
from contextlib import suppress
from paho.mqtt.client import MQTTMessage

NAME = os.environ["NAME"]
PASS = os.environ["PASS"]
LOGIN_CREDENTIALS = NAME.encode() + b"\n" + PASS.encode()

HOME_ADDR = os.environ["HOME_ADDR"]


def main():
    args = misc.get_arg_namespace()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with suppress(Exception):
        loop.create_task(mqtt_remote_send(args.port))
        loop.run_forever()
    loop.close()


async def mqtt_remote_send(port: int):
    home = AASC.AsyncAuthSockClient(
        HOME_ADDR,
        port,
        LOGIN_CREDENTIALS,
        auto_reconnect=True,
        daemon=True,
        daemon_blocking_read=True,
    )
    asyncio.create_task(home.connect())

    retained_mqtt: dict[str, m.MQTTPacket] = {}

    async def on_message(msg: MQTTMessage):
        packet = m.MQTTPacket.parse_obj(
            {"topic": msg.topic, "payload": json.loads(msg.payload), "retain": msg.retain}
        )

        if msg.retain:
            retained_mqtt[msg.topic] = packet
        elif msg.topic in retained_mqtt:
            del retained_mqtt[msg.topic]

        if home.reconnected:
            home.reconnected = False
            for _, v in retained_mqtt.items():
                asyncio.create_task(home.send(v.dict()))
        asyncio.create_task(home.send(packet.dict()))

    mqtt_settings = {
        "hostname": os.environ["HOST"],
        "port": 8883,
        "client_id": os.environ["MQTT_USER"] + "_bridge",
        "username": os.environ["MQTT_USER"],
        "password": os.environ["MQTT_PASS"],
        "tls_context": ssl.create_default_context(),
        "protocol": ProtocolVersion.V31,
    }
    while 1:
        task = None
        with suppress(Exception):
            async with MQTTClient(**mqtt_settings) as client:
                await client.subscribe(NAME + "/#", qos=1)
                task = asyncio.create_task(listen_home_then_publish(client, home))
                async with client.unfiltered_messages() as messages:
                    async for message in messages:
                        await on_message(message)
        with suppress(Exception):
            task.cancel()  # type:ignore
            await task  # type:ignore
        await asyncio.sleep(5)


async def listen_home_then_publish(mqtt: MQTTClient, home: AASC.AsyncAuthSockClient):
    while 1:
        packet = await home.recv()
        if packet is None:
            return
        packet = m.MQTTPacket.parse_obj(packet)
        if home.usrname.lower() == packet.topic.split("/", maxsplit=1)[0].lower():
            return
        asyncio.ensure_future(
            mqtt.publish(packet.topic, payload=json.dumps(packet.payload), retain=packet.retain, qos=1)
        )


if __name__ == "__main__":

    main()
