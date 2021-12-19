from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from main import db, SECRET_KEY, ACCESS_LEVELS
from pydantic import BaseModel
from jose import JWTError, jwt
from typing import Optional
import logging
import bcrypt


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str  # : Optional[str] = None


class User(BaseModel):
    username: str
    access_level: str


class UserInDB(User):
    password: str


def check_access_level(required_level: str, user_level: str) -> bool:
    return ACCESS_LEVELS[required_level] <= ACCESS_LEVELS[user_level]


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    expire = datetime.utcnow() + expires_delta if expires_delta else timedelta(minutes=15)
    to_encode = data.copy() | {"exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def validate_user(username: str, password: str) -> UserInDB | None:
    usrdata = await get_user_db(username)
    # Check if there is any rows of the user and then check password. Log failed attempts
    if usrdata and bcrypt.checkpw(password.encode(), usrdata.password.encode()):
        return usrdata
    logging.warning(time_msg("Failed login. User: " + username + " | Pass: " + password))
    return None


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"})
    try:
        username: str = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")  # type:ignore
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user_db(token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.access_level == "disabled":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_user_db(username: str) -> UserInDB | None:
    usrdata = await db.fetch_one(
        "SELECT username, password, access_level FROM users WHERE username = (:username)",
        {"username": username})
    if usrdata is None:
        return None
    return UserInDB(**{"username": usrdata[0], "password": usrdata[1], "access_level": usrdata[2]})


def time_msg(message: str) -> str:
    return datetime.now().isoformat("T")[:22] + " > " + message
