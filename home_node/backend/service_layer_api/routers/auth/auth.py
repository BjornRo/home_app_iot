import logging
from . import _auth_crud as crud
from .. import MyRouterAPI
from fastapi import Depends, HTTPException
from main import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext  # type:ignore
from pymodules.schemas import auth_schemas as schemas
from main import db_models as dbmodels


# Settings
PREFIX = "/auth"
TAGS = ["auth_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Routing
@router.get("/")
async def root():
    return {"auth": "ority"}


@router.get("/get_all", response_model=list[str])
async def get_all_users(session: AsyncSession = Depends(get_session)):
    item = await crud.get_all_users(session)
    return [i.username for i in item]


@router.post("/verify")
async def verify_user(user: schemas.UserAuth, session: AsyncSession = Depends(get_session)):
    dbusr = await crud.get_user(session, username=user.username)
    if dbusr:
        return pwd_context.verify(user.password, dbusr.password)
    return False


@router.get("/tags_all", response_model=list[str])
async def get_all_tags(session: AsyncSession = Depends(get_session)):
    return [i.tag for i in await crud.get_all_tags(session)]


@router.get("/tags/{tag_name}", response_model=schemas.Tag)
async def get_tag(tag_name: str, session: AsyncSession = Depends(get_session)):
    item = await crud.get_tag(session, tag=tag_name)
    if item is None:
        raise HTTPException(status_code=400, detail="Tag not found")
    return item


@router.post("/tags/add/{tag_name}", response_model=schemas.Tag)
async def add_tag(tag_name: str, comment: str, session: AsyncSession = Depends(get_session)):
    item = await crud.get_tag(session, tag=tag_name)
    if item is not None:
        raise HTTPException(status_code=400, detail="Tag already exist")
    return await crud.add_tag(session, tag_name, comment)


@router.delete("/tags/del/{tag_name}", response_model=schemas.Tag)
async def del_tag(tag_name: str, session: AsyncSession = Depends(get_session)):
    tag = await crud.get_tag(session, tag_name)
    if tag is None:
        raise HTTPException(status_code=400, detail="Tag doesn't exist")
    return await crud.del_tag(session, tag)


@router.post("/add_user", response_model=schemas.Users)
async def add_user(user: schemas.UserCreate, session: AsyncSession = Depends(get_session)):
    dbuser = await crud.get_user(session, username=user.username)
    if dbuser:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Check that all tags are valid
    tags_list = [i.tag for i in await crud.get_all_tags(session)]
    for i in user.usertags:
        if i not in tags_list:
            raise HTTPException(status_code=400, detail="Access Tag doesn't exist")

    # TODO remove clear passwords
    clear_pass = user.password
    user.password = pwd_context.hash(user.password)
    usr = await crud.add_user(session, user, clear_pass)

    for i in user.usertags:
        tag = await crud.add_user_tag(session, usr, i, on_add=True)
        if tag is None:
            raise HTTPException(status_code=500, detail="Something went wrong adding user tags")
    await session.refresh(usr)
    return await crud.get_user(session, user.username)


@router.get("/users/{username}", response_model=schemas.Users)
async def get_user_with_usertag_name_list(username: str, session: AsyncSession = Depends(get_session)):
    db_user = await crud.get_user(session, username=username)
    if db_user is None:
        raise HTTPException(status_code=400, detail="User not found")
    return db_user.__dict__ | {"usertags": [i.tag for i in db_user.usertags]}


@router.get("/users/{username}/detailed_tags", response_model=schemas.UsersDetailedTags)
async def get_user_with_detailed_tags(username: str, session: AsyncSession = Depends(get_session)):
    db_user = await crud.get_user(session, username=username)
    if db_user is None:
        raise HTTPException(status_code=400, detail="User not found")
    return db_user


@router.get("/users/{username}/tags", response_model=list[str])
async def get_all_user_tags(username: str, session: AsyncSession = Depends(get_session)):
    usr = await crud.get_user(session, username=username)
    if usr is None:
        raise HTTPException(status_code=400, detail="User not found")
    return [i.tag for i in usr.usertags]


@router.get("/users/{username}/tags/{tag}", response_model=schemas.UserTag)
async def get_user_tag(username: str, tag: str, session: AsyncSession = Depends(get_session)):
    usr = await crud.get_user(session, username=username)
    if usr is None:
        raise HTTPException(status_code=400, detail="User not found")
    user_tag = await crud.get_user_tag(session, usr=usr, tag=tag)
    if user_tag is None:
        raise HTTPException(status_code=400, detail="User tag not found")
    return user_tag


@router.post("/users/{username}/tags/{tag_name}", response_model=schemas.UserTag)
async def user_add_tag(username: str, tag_name: str, session: AsyncSession = Depends(get_session)):
    usr = await crud.get_user(session, username=username)
    if usr is None:
        raise HTTPException(status_code=400, detail="User not found")
    tag = await crud.get_tag(session, tag=tag_name)
    if tag is None:
        raise HTTPException(status_code=400, detail="Tag doesn't exist")
    user_tag = await crud.get_user_tag(session, usr=usr, tag=tag_name)
    if user_tag is not None:
        raise HTTPException(status_code=400, detail="User tag already exist")
    return await crud.add_user_tag(session, usr=usr, tag=tag_name, on_add=False)


@router.delete("/users/{username}/tags/{tag_name}", response_model=schemas.UserTag)
async def user_del_tag(username: str, tag_name: str, session: AsyncSession = Depends(get_session)):
    usr = await crud.get_user(session, username=username)
    if usr is None:
        raise HTTPException(status_code=400, detail="User not found")
    user_tag = await crud.get_user_tag(session, usr=usr, tag=tag_name)
    if user_tag is None:
        raise HTTPException(status_code=400, detail="User tag doesn't exist")
    return await crud.del_user_tag(session, user_tag=user_tag)


@router.delete("/users/{username}", response_model=schemas.Users)
async def del_user(username: str, db: AsyncSession = Depends(get_session)):
    db_user = await crud.get_user(db, username=username)
    if db_user is None:
        raise HTTPException(status_code=400, detail="User not found")
    return await crud.del_user(db, db_user)
