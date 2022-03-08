from . import _blocklist_schemas as dbschemas
from datetime import datetime
from db.db_models import Blocklist
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession



# Blocklist stuff
async def get_blocklist_item(session: AsyncSession, ip: str) -> Blocklist | None:
    stmt = select(Blocklist).where(Blocklist.ip == ip)
    return (await session.execute(stmt)).scalar()


async def add_blocklist_item(session: AsyncSession, obj: dbschemas.BlocklistCreate) -> Blocklist:
    default_values = dict(ban_first=datetime.utcnow(), total_attempts=1, attempt_counter=1)
    item = Blocklist(**obj.dict() | default_values)
    session.add(item)
    await session.commit()
    return item


async def del_blocklist_item(session: AsyncSession, item: Blocklist) -> Blocklist:
    await session.delete(item)
    await session.commit()
    return item


async def update_blocklist_item(
    session: AsyncSession, item: Blocklist, obj: dbschemas.BlocklistUpdate
) -> Blocklist:
    item.total_attempts += 1  # type:ignore
    item.attempt_counter = obj.attempt_counter  # type:ignore
    item.ban_expire = obj.ban_expire  # type:ignore
    await session.commit()
    return item


async def unban_blocklist_item(session: AsyncSession, item: Blocklist) -> Blocklist:
    item.ban_expire = datetime.min  # type:ignore
    item.attempt_counter = 0  # type:ignore
    await session.commit()
    return item


async def increment_attempts_blocklist_item(session: AsyncSession, item: Blocklist) -> Blocklist:
    item.total_attempts += 1  # type:ignore
    item.attempt_counter += 1  # type:ignore
    await session.commit()
    return item


async def reset_attempts(session: AsyncSession, item: Blocklist) -> Blocklist:
    item.attempt_counter = 0  # type:ignore
    await session.commit()
    return item
