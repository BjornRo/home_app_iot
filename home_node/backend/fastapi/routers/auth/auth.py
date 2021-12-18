from os import access
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from redis.commands.json import JSON as REJSON_Client

from fastapi import HTTPException, Depends, status

from typing import Optional, Dict, Union
from pydantic import BaseModel
from .. import MyRouterAPI
from ...main import db, SECRET_KEY
from jose import JWTError, jwt
import bcrypt
import redis
from datetime import datetime, timedelta

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Settings
PREFIX = "/auth"
TAGS = ["auth_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    access_level: str


class UserInDB(User):
    password: str


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_user(username: str):
    query = "SELECT username, password, access_level FROM users WHERE username = (:username)"
    usrdata = await db.fetch_one(query, {"username": username})
    if usrdata is None:
        return None
    return UserInDB(**{"username": usrdata[0], "password": usrdata[1], "access_level": usrdata[2]})


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")  # type:ignore
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(token_data.username)  # type:ignore
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.access_level == "disabled":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Following guide: (Not strictly)
# https://testdriven.io/blog/developing-a-single-page-app-with-fastapi-and-vuejs/


@router.post("/login")
async def login(payload: OAuth2PasswordRequestForm = Depends()):
    usrdata = await get_user(payload.username)
    if usrdata is None or not bcrypt.checkpw(payload.password.encode(), usrdata.password.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"}
                            )

    return {"username": payload.username, "access_level": usrdata.access_level}
