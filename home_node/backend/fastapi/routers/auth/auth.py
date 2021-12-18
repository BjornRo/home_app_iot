from redis.commands.json import JSON as REJSON_Client
from fastapi import HTTPException
from typing import Optional, Dict, Union
from pydantic import BaseModel
from .. import MyRouterAPI
import bcrypt
import redis

# Settings
PREFIX = "/auth"
TAGS = ["auth_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router


@router.post("/login")
async def login():
    try:
        user = ... # TODO get user from db,
    except:
        raise HTTPException(401,
            #status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not bcrypt.checkpw("pass".encode(), b"hash"):
        raise HTTPException(401,
            #status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return user