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
# HAS TO HAVE attribute named router
for routing in [basename(f)[:-3] for f in glob("routers/*.py") if isfile(f) and not f.endswith('__init__.py')]:
    # Each module should create a MyRouterAPI object to add itself to Classmethods list
    # Very convoluted way to fix the python typing to stop yelling at me
    # It first imports the module, thus creating the object which adds itself to class methods list.
    # Then it takes each time we create a routing, one element will be in the list, which we pop off, and then
    # add to the routing part. Better idea without using classes but then... angry hinter :-(
    import_module(f"routers.{routing}")
    app.include_router(MyRouterAPI.xs.pop())
