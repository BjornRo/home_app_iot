from . import _blocklist_schemas as schemas, _blocklist_crud as crud
from .. import MyRouterAPI
from datetime import datetime
from fastapi import Depends, HTTPException
from main import get_session
from sqlalchemy.ext.asyncio import AsyncSession

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
async def add_blocklist_ip(
    obj: schemas.BlocklistCreate, session: AsyncSession = Depends(get_session)
):
    item = await crud.get_blocklist_item(session, ip=obj.ip)
    if item:
        raise HTTPException(status_code=400, detail="IP address already exists")
    return schemas.Blocklist.from_orm(await crud.add_blocklist_item(session, obj))


# Update ban, sets datetime, attempts to the sent ones
@router.put("/", response_model=schemas.Blocklist)
async def update_blocklist_ip(
    obj: schemas.BlocklistUpdate, session: AsyncSession = Depends(get_session)
):
    item = await crud.get_blocklist_item(session, ip=obj.ip)
    if item is None:
        raise HTTPException(status_code=400, detail="IP address doesn't exist")
    return await crud.update_blocklist_item(session, item, obj)


# Get ip
@router.get("/{ip}", response_model=schemas.Blocklist)
async def get_blocklist_ip(ip: str, session: AsyncSession = Depends(get_session)):
    item = await crud.get_blocklist_item(session, ip)
    return ip_path_blocklist_item(item)


# Delete db entry for ip - should be used with caution.
@router.delete("/{ip}")
async def del_blocklist_ip(ip: str, session: AsyncSession = Depends(get_session)):
    item = await crud.get_blocklist_item(session, ip)
    if item:
        await crud.del_blocklist_item(session, item)
    return ip_path_blocklist_item(item)


# Unban ip by setting ban_expire to dt.min and attempt_counter to 0
@router.put("/{ip}", response_model=schemas.Blocklist)
async def unban_blocklist_ip(ip: str, session: AsyncSession = Depends(get_session)):
    item = await crud.get_blocklist_item(session, ip)
    if item:
        await crud.unban_blocklist_item(session, item)
    return ip_path_blocklist_item(item)


# Update attempt counter by 1 and return the current counter
@router.patch("/{ip}", response_model=int)
async def increment_attempts_blocklist_item(ip: str, session: AsyncSession = Depends(get_session)):
    item = await crud.get_blocklist_item(session, ip)
    if item:
        await crud.increment_attempts_blocklist_item(session, item)
        return item.attempt_counter
    else:
        raise HTTPException(status_code=400, detail="IP address not found")


# Helper for {ip} paths
def ip_path_blocklist_item(item):
    if item is None:
        raise HTTPException(status_code=400, detail="IP address not found")
    # "deletes" password from query
    return schemas.Blocklist.from_orm(item)


# Check if ip address is banned.
@router.get("/isbanned/{ip}", response_model=bool)
async def ip_is_banned(ip: str, session: AsyncSession = Depends(get_session)):
    item = await crud.get_blocklist_item(session, ip)
    if item:
        if datetime.utcnow() <= item.ban_expire:
            return True
        await crud.reset_attempts(session, item)
    return False
