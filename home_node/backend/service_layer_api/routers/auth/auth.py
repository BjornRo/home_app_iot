import logging
from . import _auth_db_schemas as schemas, _auth_crud as crud
from .. import MyRouterAPI
from contextlib import suppress

from main import r_conn, get_db
from datetime import datetime
from fastapi import Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from typing import Tuple
from ast import literal_eval
import ujson
from sqlalchemy.orm import Session
from sqlalchemy import func

# from . import _crud
import redis

# Settings
PREFIX = "/auth"
TAGS = ["auth_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Routing
@router.get("/")
async def root():
    return {"auth": "ority"}


@router.get("/{username}")
async def get_user(username: str, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, username=username)
    return delget_user(db_user)


@router.delete("/{username}")
async def del_user(username: str, db: Session = Depends(get_db)):
    db_user = crud.del_user(db, username=username)
    return delget_user(db_user)


def delget_user(db_user):
    if db_user is None:
        raise HTTPException(status_code=400, detail="Username not found")
    # "deletes" password from query
    return schemas.Users.from_orm(db_user)


@router.post("/add_user")
async def add_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    dbuser = crud.get_user(db, username=user.username)
    if dbuser:
        raise HTTPException(status_code=400, detail="Username already taken")
    cr = crud.add_user(db, user)
    return cr

