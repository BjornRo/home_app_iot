import aiohttp
import asyncio
import redis
import os
import ujson
from contextlib import suppress
from datetime import timedelta
from pymodules import misc as m


SECRET_KEY = m.create_or_ignore_secretkeyfile(64)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = timedelta(minutes=30)

REDIS_HOST = "rejson"

SERVICE_API = os.environ["SERVICE_API"]

r = redis.Redis(REDIS_HOST, db=int(os.getenv("DBUSRCACHE", "1")))


class AIOSession:
    session: aiohttp.ClientSession | None = None

    async def start(self):
        AIOSession.session = aiohttp.ClientSession(json_serialize=ujson.dumps)

    async def stop(self):
        with suppress(Exception):
            await AIOSession.session.close()  # type:ignore
        AIOSession.session = None

    def __call__(self) -> aiohttp.ClientSession:
        assert AIOSession.session is not None
        return AIOSession.session
