from pymodules.schemas import auth_schemas as schemas
from . import *
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import APIRouter, Cookie, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from misc import r
import ujson

# Settings
PREFIX = "/auth"
TAGS = ["auth_api"]


# To route the routings down the document.
router = APIRouter(prefix=PREFIX, tags=TAGS)  # type: ignore

# Following guide: (Not strictly)
# https://testdriven.io/blog/developing-a-single-page-app-with-fastapi-and-vuejs/
# https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/


# @router.get("/whoami", response_model=TokenData, dependencies=[Depends(get_current_user)])
# async def whoami(current_user: UserInDB = Depends(get_current_user)):
#     return TokenData(**{"username": current_user.username})


@router.post("/verify", response_model=bool)
async def verify(user: schemas.UserAuth):
    return await validate_user(user.username, user.password)


@router.get("/cookies")
async def get_cookies(access_token=Cookie(None)):
    return access_token


@router.get("/me")  # , response_model=schemas.Users)
async def read_users_me(current_user: schemas.Users = Depends(get_current_active_user)):
    return current_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    expires_delta: timedelta = ACCESS_TOKEN_EXPIRE_MINUTES,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    if not await validate_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(username=form_data.username, expires_delta=expires_delta)
    resp = JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "bearer",
        }
    )
    resp.set_cookie(key="access_token", value=access_token, httponly=True)
    return resp
