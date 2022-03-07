from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from . import _auth_db_schemas as dbschemas
from main import db_models as models

# User related stuff
def get_user(db: Session, user_id: int | None = None, username: str | None = None):
    if user_id is None and username is None:
        return None

    filter_on = (
        func.lower(models.Users.username) == func.lower(username)
        if user_id is None
        else models.Users.id == user_id
    )
    return db.query(models.Users).filter(filter_on).first()


def add_user(db: Session, user: dbschemas.UserCreate):
    usr = models.Users(**user.dict() | {"date_added": datetime.utcnow()})
    db.add(usr)
    db.commit()
    db.refresh(usr)
    return usr


def del_user(db: Session, username: str):
    usr = (
        db.query(models.Users)
        .filter(func.lower(models.Users.username) == func.lower(username))
        .first()
    )
    db.delete(usr)
    db.commit()
    return usr
