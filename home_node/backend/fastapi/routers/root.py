from . import MyRouterAPI
from starlette.responses import FileResponse

# Settings
PREFIX = ""
TAGS = ["root"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Routing
@router.get("/", include_in_schema=False)
async def root():
    return {"hello":"world"}

@router.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse("../static/favicon.ico")