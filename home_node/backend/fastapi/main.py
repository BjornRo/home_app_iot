from fastapi.middleware.cors import CORSMiddleware
from importlib import import_module
from routers import MyRouterAPI
from databases import Database
from secrets import token_hex
from datetime import datetime
from fastapi import FastAPI
from os.path import isfile
import json
import os


app = FastAPI()

ACCESS_LEVELS = {"owner": 4, "admin": 3, "mod": 2, "user": 1, "disabled": 0}

SECRET_KEY_FILE = "secretkeyfile"
# Check if secret key exists, else randomly generate one.
if not isfile(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, "w") as f:
        f.write(token_hex(32))
with open(SECRET_KEY_FILE, "r") as f:
    SECRET_KEY = f.read().strip()


DB_FILE = "main_app_db.db"  # TODO add /db/
DB_TABLES = """
CREATE TABLE users (
    username VARCHAR(20) PRIMARY KEY,
    password VARCHAR(100) NOT NULL,
    access_level VARCHAR(8) NOT NULL,
    created_date VARCHAR(19) NOT NULL,
    comment TEXT NOT NULL
)
"""

db = Database("sqlite:///" + DB_FILE)


@app.on_event("startup")
async def db_connect():
    await db.connect()

    # Check if databasefile exists
    if not isfile(DB_FILE):
        # Create db file and import tables if db-file doesn't exist
        await db.execute(query=DB_TABLES)
        query = "INSERT INTO users VALUES (:username, :password, :access_level, :created_date, :comment)"
        with open("default_users.json", "r") as f: # Default user during development. Username: admin, Password: pass
            for usr, data in json.load(f).items():
                data |= {"username": usr, "created_date": datetime.now().isoformat("T", "minutes")}
                await db.execute(query, data)


@app.on_event("shutdown")
async def db_disconnect():
    await db.disconnect()

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

# Naivly add all routes in routes folder, only need to specify the important FastAPI parts.
for dirpath, dirnames, files in os.walk("routers"):
    for module in files:
        if "__" in module or "__" in dirpath:
            continue
        # Each module should create a MyRouterAPI object which adds the router to classmethod list
        # This is a very convoluted way to fix the linter to stop yelling at me, and also easier to extend and maintain.
        # The for loop loads all the routers by popping of the stack.
        import_module('{}.{}'.format(dirpath.replace("\\", "."), module[:-3]))
        app.include_router(MyRouterAPI.xs.pop())
