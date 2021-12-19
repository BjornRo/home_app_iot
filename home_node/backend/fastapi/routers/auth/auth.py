from fastapi.security import OAuth2PasswordRequestForm
from fastapi import HTTPException, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from .. import MyRouterAPI
from . import *

# Settings
PREFIX = "/auth"
TAGS = ["auth_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Following guide: (Not strictly)
# https://testdriven.io/blog/developing-a-single-page-app-with-fastapi-and-vuejs/
# https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/


@router.get("/whoami", response_model=User, dependencies=[Depends(get_current_user)])
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    return User(**{"username": current_user.username, "access_level": current_user.access_level})


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await validate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    response = JSONResponse(content={"message": "Login successful"})
    response.set_cookie(
        "Authorization",
        value=f"Bearer {jsonable_encoder(access_token)}",
        httponly=False,
        max_age=1800,
        expires=1800,
        samesite="Lax",
        secure=False,
    )
    return response
