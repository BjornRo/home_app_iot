from fastapi.middleware.cors import CORSMiddleware
from importlib import import_module
from routers import MyRouterAPI
from fastapi import FastAPI
import json
import os


app = FastAPI()

origins = [  # Internal routing using dnsmasq on my router.
    "http://localhost",
    "http://192.168.1.173",
    "http://home.1d",
    "http://www.home",
]


# Load additonal public urls, hiding it at the moment to reduce risk of DoS attack on my own network.
url: str
with open("urls.json", "r") as f:
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
# Each router HAS TO HAVE attribute named router
for dirpath, dirnames, files in os.walk("routers"):
    for module in files:
        if module == "__init__.py":
            continue
        # Each module should create a MyRouterAPI object which adds the router to classmethod list
        # This is a very convoluted way to fix the linter to stop yelling at me, and also easier to extend and maintain.
        # The for loop loads all the routers by popping of the stack.
        import_module('{}.{}'.format(dirpath.replace("\\", "."), module[:-3]))
        app.include_router(MyRouterAPI.xs.pop())
