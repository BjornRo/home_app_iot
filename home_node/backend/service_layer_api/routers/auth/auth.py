import bcrypt
from . import _auth_db_schemas as schemas, _auth_crud as crud
from .. import MyRouterAPI
from fastapi import Depends, HTTPException
from main import get_db
from sqlalchemy.orm import Session

# Settings
PREFIX = "/auth"
TAGS = ["auth_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Routing
@router.get("/")
async def root():
    return {"auth": "ority"}


@router.post("/verify")
async def verify_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    usr = crud.get_user(db, username=user.username)
    if usr:
        return bcrypt.checkpw(user.password.encode(), usr.password.encode())
    return False


@router.post("/")
async def add_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    dbuser = crud.get_user(db, username=user.username)
    if dbuser:
        raise HTTPException(status_code=400, detail="Username already taken")
    #TODO remove clear passwords
    clear_pass = user.password
    user.password = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()
    usr = crud.add_user(db, user, clear_pass)
    return schemas.Users.from_orm(usr)


@router.get("/{username}")
async def get_user(username: str, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, username=username)
    return delget_user(db_user)


@router.delete("/{username}")
async def del_user(username: str, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, username=username)
    if db_user:
        crud.del_user(db, db_user)
    return delget_user(db_user)


def delget_user(db_user):
    if db_user is None:
        raise HTTPException(status_code=400, detail="User not found")
    # "deletes" password from query
    return schemas.Users.from_orm(db_user)




