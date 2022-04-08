from . import _errors_crud as crud
from .. import MyRouterAPI
from fastapi import Depends, HTTPException
from main import get_session
from routers.sensors import _sensors_crud
from sqlalchemy.ext.asyncio import AsyncSession
from pymodules.schemas import misc as schemas

# Settings
PREFIX = "/errors"
TAGS = ["errors_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router


@router.get("/")
async def root():
    return {"failed": "error"}


@router.get("/all", response_model=list[schemas.Error])
async def get_all_errors(session: AsyncSession = Depends(get_session)):
    return await crud.get_all_errors(session)


@router.get("/{device_name}", response_model=list[schemas.Error])
async def get_errors_device(device_name: str, session: AsyncSession = Depends(get_session)):
    dev = await _sensors_crud.get_device(session, device_name)
    if dev is None:
        raise HTTPException(status_code=422, detail="Device doesn't exist")
    return await crud.get_errors_device(session, device_name)


@router.get("/api", response_model=schemas.Error)
async def get_error(error: schemas.Error, session: AsyncSession = Depends(get_session)):
    item = await crud.get_error(session, error)
    if item:
        return item
    raise HTTPException(status_code=422, detail="Error doesn't exist")


@router.post("/api", response_model=schemas.Error)
async def add_error(error: schemas.Error, session: AsyncSession = Depends(get_session)):
    item = await crud.get_error(session, error)
    if item:
        raise HTTPException(status_code=409, detail="Error already exist")
    return await crud.add_error_item(session, error)


# Delete db entry for ip - should be used with caution.
@router.delete("/api")
async def delete_error(error: schemas.Error, session: AsyncSession = Depends(get_session)):
    item = await crud.get_error(session, error)
    if item is None:
        raise HTTPException(status_code=409, detail="Error doesn't exist")
    return await crud.add_error_item(session, error)
