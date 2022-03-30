from fastapi import APIRouter
from starlette.responses import FileResponse
from datetime import datetime

# Settings
PREFIX = ""
TAGS = ["root"]

# To route the routings down the document.
router = APIRouter(prefix=PREFIX, tags=TAGS)  # type: ignore


@router.get("/", include_in_schema=False)
async def root():
    return {"hello": "world"}


@router.get("/time", include_in_schema=False, response_model=datetime)
async def time():
    return datetime.utcnow()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")
