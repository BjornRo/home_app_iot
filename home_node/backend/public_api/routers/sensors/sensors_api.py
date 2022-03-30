from misc import SERVICE_API, AIOSession
from fastapi import HTTPException, APIRouter
from pymodules.schemas.sensors_schemas import LocationSensorData, RelayStatus

# Settings
PREFIX = "/sensors"
TAGS = ["sensors_api"]

# To route the routings down the document.
router = APIRouter(prefix=PREFIX, tags=TAGS)  # type: ignore

session = AIOSession()

# Examples
api_responses = {
    200: {
        "description": "Sensor API data",
        "content": {
            "application/json": {
                "example": {
                    "home": {
                        "balcony": {
                            "time": "2021-12-31T13:37:59.12345",
                            "new": True,
                            "data": {
                                "temperature": 42,
                                "humidity": 33.4,
                            },
                        },
                        "bikeroom": {
                            "time": "2021-12-31T00:13:37.12345",
                            "new": True,
                            "data": {
                                "temperature": -42,
                            },
                        },
                        "kitchen": {
                            "time": "2021-12-31T11:13:37.12345",
                            "new": True,
                            "data": {"temperature": -42, "humidity": 99.9, "airpressure": 1024.64},
                        },
                    },
                    "remote_sh": {
                        "pizw": {
                            "time": "2021-12-31T13:37:59.12345",
                            "new": True,
                            "data": {
                                "temperature": 42,
                            },
                        },
                        "hydrofor": {
                            "time": "2021-12-31T00:13:37.12345",
                            "new": True,
                            "data": {"temperature": -42, "humidity": 99.9, "airpressure": 999.9},
                        },
                    },
                }
            }
        },
    },
    204: {},
}


# Routing
@router.get("/", response_model=LocationSensorData, responses=api_responses)  # type:ignore
async def get_sensor_data():
    resp = await session().get(f"{SERVICE_API}/sensors")
    if resp.status >= 300:
        raise HTTPException(status_code=500)
    return await resp.json()


# Routing
@router.get("/relay_status", response_model=RelayStatus)
async def relay_status():
    resp = await session().get(f"{SERVICE_API}/sensors/home/balcony/relay/status")
    if resp.status >= 300:
        raise HTTPException(status_code=500)
    return await resp.json()
