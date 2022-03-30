import argparse
import os
import ujson
import uvicorn
from misc import AIOSession
from routers import root
from routers.auth import auth
from routers.sensors import sensors_api
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware


app = FastAPI()

app.add_middleware(HTTPSRedirectMiddleware)
origins = [  # Internal routing using dnsmasq on my router.
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:7070",
    "http://192.168.1.173",
    "http://home.1d",
    "http://www.home",
] + [j + i for i in ujson.loads(os.environ["EXTRA_URLS"]) for j in ["http://", "https://"]]

session = AIOSession()

@app.on_event("startup")
async def startup_event():
    await session.start()


@app.on_event("shutdown")
async def shutdown_event():
    await session.stop()


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(root.router)
app.include_router(auth.router)
app.include_router(sensors_api.router)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_const", dest="reload", const=True, default=False)
    parser.add_argument(
        "-p",
        "--port",
        help="Port number",
        dest="port",
        type=int,
        default=8000,
        metavar="{0..65535}",
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="Print lots of debugging statements",
        action="store_const",
        dest="loglevel",
        const="debug",
        default="warning",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Be verbose",
        action="store_const",
        dest="loglevel",
        const="info",
    )
    args = parser.parse_args()

    uvicorn.run(
        "main:app",  # type: ignore
        host="0.0.0.0",
        port=args.port,
        log_level=args.loglevel,
        reload=args.reload,
        ssl_keyfile=f'/etc/letsencrypt/live/{os.environ["HOSTNAME"]}/privkey.pem',
        ssl_certfile=f'/etc/letsencrypt/live/{os.environ["HOSTNAME"]}/fullchain.pem',
    )
