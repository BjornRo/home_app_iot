import os
import redis
import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from importlib import import_module
from redis.commands.json import JSON as REJSON_Client
from routers import MyRouterAPI
from typing import AsyncGenerator


import db.db_models as db_models
from db.db_config import engine, async_session


app = FastAPI()


# Redis json to be able to communicate between the daemon and backend.
REJSON_HOST = "rejson"
# TODO Change to async redis client
r_conn: REJSON_Client = redis.Redis(
    host=REJSON_HOST, port=6379, db=int(os.getenv("DBSENSOR", "0"))
).json()


# Db
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        #await conn.run_sync(db_models.Base.metadata.drop_all)
        await conn.run_sync(db_models.Base.metadata.create_all)


async def get_session() -> AsyncGenerator:
    async with async_session() as session:
        yield session


origins = [  # Internal routing using dnsmasq on my router.
    "http://localhost",
    "http://home.1d",
    "http://192.168.1.173",
    "http://192.168.1.199",
    "http://192.168.1.200",
    "http://www.home",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


for dirpath, _, files in os.walk("routers"):
    path = pathlib.Path(dirpath)
    # Ignore folders with _
    if path.match("_*"):
        continue

    # Find loadable modules without _
    for module in files:
        # Don't load files/folders starting with '_'.
        # Also works as commenting out routings; _routerNameFolder
        if module.startswith("_"):
            continue
        # Each module should create a MyRouterAPI object which adds the routers to a list which the Class contains.
        # This is a very convoluted way to fix the linter to stop yelling at me, and also easier to extend and maintain.
        # The for loop loads the module which creates a router and adds to list in class, which we pop off and include to FastAPI.
        import_module(f'{path.as_posix().replace("/", ".")}.{module.replace(".py", "")}')
        app.include_router(MyRouterAPI.xs.pop())
