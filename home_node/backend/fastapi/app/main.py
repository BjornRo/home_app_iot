import json
import redis
from redis.commands.json import JSON as REJSON_Client
from datetime import date
from fastapi import FastAPI
from importlib import import_module
from glob import glob
from os.path import basename, isfile
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import MyRouterAPI

app = FastAPI()

# Naivly add all routes in routes folder, only need to specify the important FastAPI parts.
# Each router HAS TO HAVE attribute named router
for routing in [basename(f)[:-3] for f in glob("routers/*.py") if isfile(f) and not f.endswith('__init__.py')]:
    # Each module should create a MyRouterAPI object which adds the router to classmethod list
    # This is a very convoluted way to fix the linter to stop yelling at me, and also easier to extend and maintain.
    # The for loop loads all the routers by popping of the stack.
    import_module(f"routers.{routing}")
    app.include_router(MyRouterAPI.xs.pop())
