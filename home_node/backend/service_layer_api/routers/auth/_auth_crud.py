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


# TODO remove clear_password
def add_user(db: Session, user: dbschemas.UserCreate, clear_password: str):
    usr = models.Users(**user.dict() | {"date_added": datetime.utcnow()})
    db.add(usr)
    db.commit()
    db.refresh(usr)
    # Todo remove
    pw = models.UserPasswordCleartext(**dict(userid=usr.id, clear_password=clear_password))
    db.add(pw)
    db.commit()
    db.refresh(pw)
    return usr


def del_user(db: Session, user: models.Users):
    uid = user.id
    db.delete(user)

    desc = db.query(models.UserDescription).filter(models.UserDescription.userid == uid).first()
    if desc:
        db.delete(desc)

    # TODO Remove
    clear_pw = db.query(models.UserPasswordCleartext).filter(models.UserPasswordCleartext.userid == uid).first()
    if clear_pw:
        db.delete(clear_pw)
    db.commit()
    return user

