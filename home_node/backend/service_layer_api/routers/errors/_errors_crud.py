from db.db_models import Error
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pymodules.schemas import misc as schemas


async def get_errors_device(session: AsyncSession, device_name: str) -> list[Error]:
    stmt = select(Error).where(Error.device_name == device_name.lower())
    return (await session.execute(stmt)).scalars().all()


async def get_all_errors(session: AsyncSession) -> list[Error] | None:
    return (await session.execute(select(Error))).scalars().all()


async def get_error(session: AsyncSession, item: schemas.Error) -> Error | None:
    stmt = select(Error).where(and_(Error.device_name == item.device_name.lower(), Error.time == item.time))
    return (await session.execute(stmt)).scalar()


async def add_error_item(session: AsyncSession, obj: schemas.Error) -> Error:
    obj.device_name = obj.device_name.lower()
    item = Error(**obj.dict())
    session.add(item)
    await session.commit()
    return item


async def del_error_item(session: AsyncSession, item: Error) -> Error:
    await session.delete(item)
    await session.commit()
    return item
