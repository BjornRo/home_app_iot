from pydantic import BaseModel
from datetime import datetime


class UsersBase(BaseModel):
    username: str


class Users(UsersBase):
    id: int
    date_added: datetime

    class Config:
        orm_mode = True


class UserCreate(UsersBase):
    password: str


class UserDescription(BaseModel):
    userid: int
    text: str