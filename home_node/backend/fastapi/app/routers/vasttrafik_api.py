from typing import Union, List
from pydantic import BaseModel
from fastapi import HTTPException
from . import MyRouterAPI
import json
import pymemcache


# Settings
PREFIX = "/vasttrafik"
TAGS = ["vasttrafik_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Memcache to be able to communicate between the daemon and backend.
mc = pymemcache.Client("memcached")


# JSON Schemas
class VasttrafikLineColors(BaseModel):
    fgColor: str
    bgColor: str
    stroke: str


class VasttrafikLineData(BaseModel):
    endstation: str
    id: str
    next: List[int]
    track: str
    colors: VasttrafikLineColors


class VasttrafikItem(BaseModel):
    time: str
    data: List[VasttrafikLineData]


# Examples
api_responses = {
    200: {
        "description": " Vasttrafik parsed API data",
        "content": {
            "application/json": {
                "example": {
                    "time": "2021-12-31T23:59",
                    "data": [{
                        "endstation": "Angered",
                        "id": "8",
                        "next": [-1, 0, 24, 42],
                        "track": "C",
                        "colors": {
                            "bgColor": "#A5449A",
                            "fgColor": "#FFFFFF",
                            "stroke": "Solid",
                        }
                    },
                        {
                        "endstation": "Centralstationen",
                        "id": 'X',
                        "next": [23],
                        "track": "C",
                        "colors": {
                            "bgColor": "#AAAAAA",
                            "fgColor": "#FFFFFF",
                            "stroke": "Solid",
                        }
                    }]
                }
            }
        }
    },
    204: {}
}


# Routing
@router.get("/api",
            response_model=VasttrafikItem,
            responses=api_responses,  # type:ignore
            )
async def api():
    data = json.loads(mc.get("vasttrafik_api_data"))
    if data is None:
        raise HTTPException(status_code=204)
    return data


# @app.get("/", status_code=404, responses={404: {"description": ":-(", "content": {"application/json": {"example": "null"}}}})
# async def root():
#     return JSONResponse(status_code=404)
