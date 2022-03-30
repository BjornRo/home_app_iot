from pydantic import BaseModel
from datetime import datetime


class Tag(BaseModel):
    tag: str
    comment: str
    created_date: datetime

    class Config:
        orm_mode = True


class UserTag(BaseModel):
    user_id: int
    tag: str
    date_granted: datetime

    class Config:
        orm_mode = True


class UsersBase(BaseModel):
    username: str


class UsersDetailedTags(UsersBase):
    id: int
    date_added: datetime
    usertags: list[UserTag]

    class Config:
        orm_mode = True

class Users(UsersBase):
    id: int
    date_added: datetime
    usertags: list[str]

    class Config:
        orm_mode = True


class UserAuth(UsersBase):
    password: str


class UserCreate(UsersBase):
    password: str
    usertags: list[str]


class UserDescription(BaseModel):
    userid: int
    text: str
