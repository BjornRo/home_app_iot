from pymodules.schemas import auth_schemas as dbschemas
from datetime import datetime
from db.db_models import UserTags, Users, UserDescription, UserPasswordCleartext, AccessTags
from sqlalchemy import func, select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


# User related stuff
async def get_user(session: AsyncSession, username: str) -> Users | None:
    stmt = (
        select(Users)
        .where(func.lower(Users.username) == username.lower())
        .options(selectinload(Users.usertags))
    )
    return (await session.execute(stmt)).scalar()


async def get_all_users(session: AsyncSession) -> list[Users]:
    return (await session.execute(select(Users))).scalars().all()


# Tags
async def get_tag(session: AsyncSession, tag: str) -> AccessTags | None:
    stmt = select(AccessTags).where(AccessTags.tag == tag.lower())
    return (await session.execute(stmt)).scalar()


async def get_all_tags(session: AsyncSession) -> list[AccessTags]:
    stmt = select(AccessTags)
    return (await session.execute(stmt)).scalars().all()


async def add_tag(session: AsyncSession, tag: str, comment: str) -> AccessTags:
    tag_db = AccessTags(tag=tag.lower(), created_date=datetime.utcnow(), comment=comment)
    session.add(tag_db)
    await session.commit()
    return tag_db


async def del_tag(session: AsyncSession, tag: AccessTags) -> AccessTags:
    await session.delete(tag)
    await session.commit()
    return tag


async def add_user_tag(session: AsyncSession, usr: Users, tag: str, on_add: bool) -> UserTags | None:
    user_tag = UserTags(user_id=usr.id, tag=tag, date_granted=datetime.min if on_add else datetime.utcnow())
    session.add(user_tag)
    await session.commit()
    return user_tag


async def get_user_tag(session: AsyncSession, usr: Users, tag: str) -> UserTags | None:
    stmt = select(UserTags).where(and_(UserTags.user_id == usr.id, UserTags.tag == tag.lower()))
    return (await session.execute(stmt)).scalar()


async def del_user_tag(session: AsyncSession, user_tag: UserTags) -> UserTags | None:
    await session.delete(user_tag)
    await session.commit()
    return user_tag


# TODO remove clear_password
async def add_user(session: AsyncSession, user: dbschemas.UserCreate, clear_password: str) -> Users:
    usr = Users(**user.dict() | {"date_added": datetime.utcnow(), "usertags": []})
    session.add(usr)
    await session.commit()
    # Todo remove
    session.add(UserPasswordCleartext(**dict(userid=usr.id, clear_password=clear_password)))
    await session.commit()
    return usr


async def del_user(session: AsyncSession, user: Users) -> Users:
    uid = user.id
    await session.delete(user)
    # await session.execute(delete(UserDescription).where(UserDescription.userid == uid))
    # TODO Remove
    await session.execute(delete(UserPasswordCleartext).where(UserPasswordCleartext.userid == uid))
    await session.commit()
    return user
