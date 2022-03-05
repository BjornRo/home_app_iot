from fastapi.middleware.cors import CORSMiddleware
from redis.commands.json import JSON as REJSON_Client
from importlib import import_module
from routers import MyRouterAPI
from databases import Database
from secrets import token_hex
from datetime import datetime
from fastapi import FastAPI
from os.path import isfile
import json
from glob import glob
import redis
import pathlib
import os
from os.path import basename, isfile
import sys


app = FastAPI()


REJSON_HOST = "rejson"
# Redis json to be able to communicate between the daemon and backend.
r_conn: REJSON_Client = redis.Redis(
    host=REJSON_HOST, port=6379, db=int(os.getenv("DBSENSOR", "0"))
).json()


origins = [  # Internal routing using dnsmasq on my router.
    "http://localhost",
    "http://192.168.1.173",
    "http://home.1d",
    "http://www.home",
]

# Load additonal public urls, hiding it at the moment to reduce risk of DoS attack on my own network.
url: str
with open("hidden_urls.json", "r") as f:
    for url in json.load(f)["urls"]:
        origins.append("http://" + url)
        origins.append("https://" + url)


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
