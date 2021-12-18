from fastapi.security import OAuth2PasswordRequestForm

from redis.commands.json import JSON as REJSON_Client

from fastapi import HTTPException, Depends, status

from typing import Optional, Dict, Union
from pydantic import BaseModel
from .. import MyRouterAPI
from ...main import db
import bcrypt
import redis

# Settings
PREFIX = "/auth"
TAGS = ["auth_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Following guide: (Not strictly)
# https://testdriven.io/blog/developing-a-single-page-app-with-fastapi-and-vuejs/
@router.post("/login")
async def login(payload: OAuth2PasswordRequestForm = Depends()):
    usrdata = await db.fetch_one("SELECT username, password, access_level FROM users WHERE username = (:username)", {"username": payload.username})
    if usrdata is None or not bcrypt.checkpw(payload.password.encode(), usrdata[1].encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"}
                            )
    return {"username": payload.username, "access_level": usrdata[2]}
