from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from . import _blocklist_schemas as dbschemas
from main import db_models as models


# Blocklist stuff
def get_blocklist_item(db: Session, ip: str):
    return db.query(models.Blocklist).filter(models.Blocklist.ip == ip).first()


# BlocklistCreate.parse_obj({"ip":"111.111", "ban_expire": datetime.max, "manual_ban": False})
def add_blocklist_item(db: Session, obj: dbschemas.BlocklistCreate):
    default_values = dict(ban_first=datetime.utcnow(), total_attempts=1, attempt_counter=1)
    item = models.Blocklist(**obj.dict() | default_values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def del_blocklist_item(db: Session, ip: str):
    item = db.query(models.Blocklist).filter(models.Blocklist.ip == ip).first()
    db.delete(item)
    db.commit()
    return item


# {"ip":"22"} | {"ip":"111.111", "ban_expire": datetime.max, "manual_ban": False}
def update_blocklist_item(db: Session, obj: dbschemas.BlocklistUpdate):
    item = db.query(models.Blocklist).filter(models.Blocklist.ip == obj.ip).first()
    if item is None:
        return None
    item.total_attempts += 1  # type:ignore
    item.attempt_counter = 0  # type:ignore
    item.ban_expire = obj.ban_expire  # type:ignore
    db.commit()
    db.refresh(item)
    return item


def unban_blocklist_item(db: Session, ip: str):
    item = db.query(models.Blocklist).filter(models.Blocklist.ip == ip).first()
    if item is None:
        return None
    item.ban_expire = datetime.min  # type:ignore
    item.attempt_counter = 0  # type:ignore
    db.commit()
    db.refresh(item)
    return item


def increment_attempts_blocklist_item(db: Session, ip: str):
    item = db.query(models.Blocklist).filter(models.Blocklist.ip == ip).first()
    if item is None:
        return None
    item.total_attempts += 1  # type:ignore
    item.attempt_counter += 1  # type:ignore
    db.commit()
    db.refresh(item)
    return item
