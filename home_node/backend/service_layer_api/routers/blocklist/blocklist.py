import logging
import ujson
from . import _blocklist_schemas as schemas, _blocklist_crud as crud
from .. import MyRouterAPI
from contextlib import suppress
from datetime import datetime
from fastapi import Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from main import r_conn, get_db
from sqlalchemy.orm import Session


# Settings
PREFIX = "/blocklist"
TAGS = ["blocklist_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Routing
@router.get("/")
async def root():
    return {"block": "list"}

# Add ban
@router.post("/")
async def add_blocklist_ip(obj: schemas.BlocklistCreate, db: Session = Depends(get_db)):
    dbuser = crud.get_blocklist_item(db, ip=obj.ip)
    if dbuser:
        raise HTTPException(status_code=400, detail="IP address already exists")
    cr = crud.add_blocklist_item(db, obj)
    return cr


# Update ban, sets datetime, attempts to the sent ones
@router.put("/")
async def update_blocklist_ip(obj: schemas.BlocklistUpdate, db: Session = Depends(get_db)):
    dbuser = crud.get_blocklist_item(db, ip=obj.ip)
    if dbuser is None:
        raise HTTPException(status_code=400, detail="IP address doesn't exist")
    cr = crud.update_blocklist_item(db, obj)
    return cr


# Get ip
@router.get("/{ip}")
async def get_blocklist_ip(ip: str, db: Session = Depends(get_db)):
    db_user = crud.get_blocklist_item(db, ip)
    return ip_path_blocklist_item(db_user)


# Delete db entry for ip - should be used with caution.
@router.delete("/{ip}")
async def del_blocklist_ip(ip: str, db: Session = Depends(get_db)):
    db_user = crud.del_blocklist_item(db, ip)
    return ip_path_blocklist_item(db_user)


# Unban ip by setting ban_expire to dt.min and attempt_counter to 0
@router.put("/{ip}")
async def unban_blocklist_ip(ip: str, db: Session = Depends(get_db)):
    db_user = crud.unban_blocklist_item(db, ip)
    return ip_path_blocklist_item(db_user)


# Update attempt counter by 1 and return the current counter
@router.patch("/{ip}")
async def increment_attempts_blocklist_item(ip: str, db: Session = Depends(get_db)):
    db_user = crud.increment_attempts_blocklist_item(db, ip)
    item = ip_path_blocklist_item(db_user)
    return item.attempt_counter


# Helper for {ip} paths
def ip_path_blocklist_item(db_user):
    if db_user is None:
        raise HTTPException(status_code=400, detail="IP address not found")
    # "deletes" password from query
    return schemas.Blocklist.from_orm(db_user)


# Check if ip address is banned.
@router.get("/isbanned/{ip}")
async def ip_is_banned(ip: str, db: Session = Depends(get_db)):
    db_user = crud.get_blocklist_item(db, ip)
    if db_user:
        if datetime.utcnow() <= db_user.ban_expire:
            return True
        crud.reset_attempts(db, db_user)
    return False


