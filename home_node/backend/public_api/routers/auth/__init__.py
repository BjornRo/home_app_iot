import json
import logging
import redis
import os
import ujson
from pymodules.schemas import auth_schemas as schemas
from datetime import datetime, timedelta
from fastapi import Cookie, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from misc import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY, SERVICE_API, r, AIOSession
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


session = AIOSession()

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str  # : Optional[str] = None


def create_access_token(username: str, expires_delta: timedelta | None = None):
    return jwt.encode(
        {
            "sub": username,
            "exp": datetime.utcnow() + expires_delta if expires_delta else ACCESS_TOKEN_EXPIRE_MINUTES,
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


async def validate_user(username: str, password: str) -> bool:
    payload = {"username": username, "password": password}
    resp = await session().post(f"{SERVICE_API}/auth/verify", json=payload)
    return (await resp.text()).lower() == "true"


async def get_user(username: str) -> None | schemas.Users:
    name_low = username.lower()
    data: None | bytes | str = r.get(name_low)
    if data is None:
        resp = await session().get(f"{SERVICE_API}/auth/users/{name_low}")
        if resp.status >= 300:
            return None
        data = await resp.text()
        r.set(name_low, data)
        r.expire(name_low, ACCESS_TOKEN_EXPIRE_MINUTES)
    return schemas.Users.parse_raw(data)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_dict = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = token_dict.get("sub")  # type:ignore
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = await get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: schemas.Users = Depends(get_current_user)) -> schemas.Users:
    if "disabled" in current_user.usertags:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
