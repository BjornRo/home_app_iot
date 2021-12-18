from redis.commands.json import JSON as REJSON_Client
from fastapi import HTTPException
from typing import Optional, Dict, Union
from pydantic import BaseModel
from . import MyRouterAPI
import redis

# Settings
PREFIX = "/sensor"
TAGS = ["sensor_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Redis json to be able to communicate between the daemon and backend.
REJSON_HOST = "rejson"
r_conn: REJSON_Client = redis.Redis(host=REJSON_HOST, port=6379, db=0).json()


# Data models
class Data(BaseModel):
    # TODO use '|' asap pydantic is updated
    __root__: Dict[str, Union[float, int, str]]


class DeviceData(BaseModel):
    time: str
    new: bool
    data: Data


class SensorData(BaseModel):
    __root__: Dict[str, Dict[str, DeviceData]]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]


# Examples
api_responses = {
    200: {
        "description": "Sensor API data",
        "content": {
            "application/json": {
                "example": {
                    "home": {
                        "balcony": {
                            "time": "2021-12-31T13:37:59.12345",
                            "new": True,
                            "data": {
                                "temperature": 42,
                                "humidity": 33.4,
                            }
                        },
                        "bikeroom": {
                            "time": "2021-12-31T00:13:37.12345",
                            "new": True,
                            "data": {
                                "temperature": -42,
                            }
                        },
                        "kitchen": {
                            "time": "2021-12-31T11:13:37.12345",
                                    "new": True,
                                    "data": {
                                        "temperature": -42,
                                        "humidity": 99.9,
                                        "airpressure": 1024.64
                                    }
                        },
                    },
                    "remote_sh": {
                        "pizw": {
                            "time": "2021-12-31T13:37:59.12345",
                            "new": True,
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
                    },
                }
            }
        }
    },
    204: {}
}


# Routing
@ router.get("/api",
             response_model=SensorData,
             responses=api_responses,  # type:ignore
             )
async def api():
    data: Optional[dict] = r_conn.get("sensors")
    if data:
        return data
    return HTTPException(status_code=204)
