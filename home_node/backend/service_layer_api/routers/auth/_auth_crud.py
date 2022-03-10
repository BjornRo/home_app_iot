from . import _auth_db_schemas as dbschemas
from datetime import datetime
from db.db_models import Users, UserDescription, UserPasswordCleartext
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# User related stuff
async def get_user(
    session: AsyncSession, user_id: int | None = None, username: str | None = None
) -> Users | None:
    if user_id is None and username is None:
        return None

    stmt = select(Users).where(
        func.lower(Users.username) == func.lower(username)
        if user_id is None
        else Users.id == user_id
    )
    return (await session.execute(stmt)).scalar()


# TODO remove clear_password
async def add_user(session: AsyncSession, user: dbschemas.UserCreate, clear_password: str) -> Users:
    usr = Users(**user.dict() | {"date_added": datetime.utcnow()})
    session.add(usr)
    await session.commit()
    # Todo remove
    session.add(UserPasswordCleartext(**dict(userid=usr.id, clear_password=clear_password)))
    await session.commit()
    return usr


async def del_user(session: AsyncSession, user: Users) -> Users:
    uid = user.id
    await session.delete(user)
    #await session.execute(delete(UserDescription).where(UserDescription.userid == uid))
    # TODO Remove
    await session.execute(delete(UserPasswordCleartext).where(UserPasswordCleartext.userid == uid))
    await session.commit()
    return user
