from typing import Optional, Union, List, Dict
from pydantic import BaseModel
from fastapi import HTTPException
from . import MyRouterAPI
import json
from datetime import datetime
import pymemcache
from base64 import b64decode, b64encode


# Settings
PREFIX = "/news"
TAGS = ["news_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Memcache to be able to communicate between the daemon and backend.
mc = pymemcache.Client("memcached")


# JSON Schemas
class NewsItem(BaseModel):
    sticky: bool
    enddate: Optional[str]
    postdate: str
    image: Optional[str]
    title: str
    text: str


class NewsData(BaseModel):
    time: str
    data: List[NewsItem]


# Examples
api_responses = {
    200: {
        "description": "News API data",
        "content": {
            "application/json": {
                "example": {
                    "time": "2021-12-31T23:59:8.1111",
                    "data": [
                        {"sticky": True, "enddate": "2044-12-31T00:11", "postdate": "2021-12-31T23:59:7.1111", "image": "image.png", "title": "Headline title",
                            "text": "Integer pellentesque ex sit amet diam auctor, et maximus mauris semper. Vivamus ac diam scelerisque libero ultricies ornare hendrerit eget lectus."},
                        {"sticky": False, "enddate": None, "postdate": "2021-01-31T23:59:7.1111", "image": "image.jpg", "title": "Headline title 2",
                            "text": "Vivamus ac diam scelerisque libero ultricies ornare hendrerit eget lectus."},
                        {"sticky": False, "enddate": "2024-12-31T00:11:59.99999", "postdate": "1940-01-04T00:01:09.11", "image": "long ass binary string", "title": "Headline title",
                            "text": "Integer pellentesque ex sit amet diam auctor, et maximus mauris semper. Vivamus ac diam scelerisque libero ultricies ornare hendrerit eget lectus."},
                        {"sticky": True, "enddate": "8008-12-31T00:11:59", "postdate": "1922-01-04T00:01:09.11", "image": None, "title": "Oops I",
                            "text": "Did it again..."},
                    ]
                }
            }
        }
    },
    204: {}
}


# Routing
@ router.get("/api/{n_items}",
             response_model=NewsData,
             responses=api_responses,  # type:ignore
             )
async def api(n_items: str):
    data = json.loads(mc.get("news_api_data"))
    try:
        n = int(n_items)
    except:
        n = 0
    if data is None:
        raise HTTPException(status_code=204)
    return data
