from . import MyRouterAPI
from starlette.responses import FileResponse

# Settings
PREFIX = ""
TAGS = ["root"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Routing


@router.get("/", include_in_schema=False)
async def root():
    return {"hello": "world"}


@router.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


@router.get('/balc_status', include_in_schema=False)
async def balc_status():
    return {"status": [0, 0, 1, 0]}


@router.get('/sensor_resp', include_in_schema=False)
async def sensor_resp():
    return {
        "home": {
            "balcony": {
                "time": "2021-12-31T13:37:59.12345",
                "new": True,
                "data": {
                    "temperature": 42.1,
                    "humidity": 33.4,
                }
            },
            "bikeroom": {
                "time": "2021-12-31T00:13:37.12345",
                "new": True,
                "data": {
                    "temperature": -42.4,
                }
            },
            "kitchen": {
                "time": "2021-12-31T11:13:37.12345",
                "new": True,
                "data": {
                    "temperature": -42.3,
                    "humidity": 99.9,
                    "airpressure": 1024.64
                }
            },
        },
        "remote_sh": {
            "pizw": {
                "time": "2021-12-31T13:37:59.12345",
                "new": False,
                "data": {
                    "temperature": 42,
                }
            },
            "hydrofor": {
                "time": "2021-12-31T00:13:37.12345",
                "new": True,
                "data": {
                    "temperature": -42,
                    "humidity": 99.9,
                    "airpressure": 999.9
                }
            }
        }
    }
