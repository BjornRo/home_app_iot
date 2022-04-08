import asyncio
import logging
import os
import ujson
from sensor_logger.main import HOME_ADDR
from pymodules import datamodels as m, misc, AsyncAuthSockClient as AASC
from asyncio_mqtt import Client
from contextlib import suppress
from paho.mqtt.client import MQTTMessage

NAME = os.environ["NAME"]
PASS = os.environ["PASS"]
LOGIN_CREDENTIALS = NAME.encode() + b"\n" + PASS.encode()

HOME_ADDR = os.environ["HOME_ADDR"]


def main():
    args = misc.get_arg_namespace()

    logging.info("MQTT net bridge client: started.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with suppress(Exception):
        loop.create_task(mqtt_remote_send(args.port))
        loop.run_forever()
    loop.close()

    logging.warning("MQTT net bridge client: exited...")


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
        payload: dict[str, float] = ujson.loads(msg.payload)
        packet = m.MQTTPacket.parse_obj({"topic": msg.topic, "payload": payload, "retain": msg.retain})

        if msg.retain:
            retained_mqtt[msg.topic] = packet
        elif msg.topic in retained_mqtt:
            retained_mqtt.pop(msg.topic)

        # If a reconnection occurs
        if home.reconnected:
            home.reconnected = False
            for _, v in retained_mqtt.items():
                asyncio.create_task(home.send(v.dict()))
        asyncio.create_task(home.send(packet.dict()))

    mqtt_settings = {
        "hostname": "mqtt.lan",
        "client_id": os.environ["MQTT_USER"] + "_bridge",
        "username": os.environ["MQTT_USER"],
        "password": os.environ["MQTT_PASS"],
    }
    while 1:
        task = None
        with suppress(Exception):
            async with Client(**mqtt_settings) as client:
                logging.info("Logged into mqtt.")
                await client.subscribe(NAME + "/#")
                task = asyncio.create_task(mqtt_sock_publish(client, home))
                async with client.unfiltered_messages() as messages:
                    async for message in messages:
                        await on_message(message)
        with suppress(Exception):
            home._buffer.put_nowait(None)
        with suppress(Exception):
            task.cancel()  # type:ignore
            await task  # type:ignore
        logging.info("Disconnected from mqtt...")
        await asyncio.sleep(5)


async def mqtt_sock_publish(mqtt: Client, home: AASC.AsyncAuthSockClient):
    while 1:
        packet = await home.recv()
        if packet is None:
            return
        payload = m.MQTTPacket.parse_obj(packet)
        if home.usrname.lower() != payload.topic.split("/")[0].lower():
            asyncio.ensure_future(
                mqtt.publish(payload.topic, payload=ujson.dumps(payload.payload), retain=payload.retain)
            )


if __name__ == "__main__":

    main()
