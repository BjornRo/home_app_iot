import logging
from ._func import _set_json, _test_value, _transform_to_dict
from .. import MyRouterAPI
from main import r_conn
from datetime import datetime
from fastapi import HTTPException, Response
from typing import List


# Settings
PREFIX = "/sensors"
TAGS = ["sensors_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router


# Routing
@router.get("/")
async def root():
    data: dict | None = r_conn.get("sensors")
    if data:
        return data
    raise HTTPException(status_code=404)


@router.get("/{location}/{device}")
async def get_data(location: str, device: str):
    return r_conn.get("sensors", f".{location}.{device}")


@router.post("/{location}/{device}")
async def post_data(location: str, device: str, data: dict | list | int | float | str):
    data_dict = _transform_to_dict(data)
    if data_dict is not None:
        new_data = {}
        for k, v in data_dict.items():
            value = _test_value(location, k, v)
            if value is None:
                data_dict = None
                break
            new_data[k] = value
        else:
            _set_json(r_conn, f".home.{device}.data", new_data)
            _set_json(r_conn, f".home.{device}.time", datetime.utcnow().isoformat("T"))
            _set_json(r_conn, f".home.{device}.new", True)
    if data_dict is None:
        logging.warning(f"Sensors data malformed: {device}, {str(data)[:15]}")
    return Response(status_code=204)


@router.post("/home/balcony/relay/status")
async def post_relay_status(data: List[int]):
    if not set(data).difference(set((0, 1))) and len(data) == 4:
        _set_json(r_conn, ".home.balcony.relay.status", data)
    else:
        logging.warning("Status data malformed: " + str(data)[:26])
    return Response(status_code=204)


@router.get("/home/balcony/relay/status")
async def get_relay_status():
    return r_conn.get("sensors", ".home.balcony.relay.status")
