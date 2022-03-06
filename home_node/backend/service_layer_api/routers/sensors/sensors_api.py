import logging
from . import _func as f
from .. import MyRouterAPI
from contextlib import suppress
from main import r_conn, get_db
from datetime import date, datetime
from fastapi import Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from typing import List, Dict
from ast import literal_eval
import json
from sqlalchemy.orm import Session
from pydantic import BaseModel
from . import _crud, _schemas
import redis

# Settings
PREFIX = "/sensors"
TAGS = ["sensors_api"]

# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router


class MeasurementData(BaseModel):
    __root__: Dict[str, float | int]


class Data(BaseModel):
    data: MeasurementData
    time: datetime
    new: bool


class DeviceData(BaseModel):
    __root__: Dict[str, Data]


class LocationSensorData(BaseModel):
    __root__: Dict[str, DeviceData]


# Routing
@router.get("/")
async def root():
    data: dict | None = r_conn.get("sensors")
    if data:
        return data
    raise HTTPException(status_code=404)


# Routing
@router.get("/data")
async def get_sensor_data():
    data: dict | None = r_conn.get("sensors")
    if data:
        with suppress(KeyError):
            del data["home"]["balcony"]["relay"]
        return data
    raise HTTPException(status_code=404)


@router.post("/{location}")
async def post_location_data(location: str, request: Request):
    data_string = (await request.body()).decode()
    try:
        payload = json.loads(data_string)
    except:
        try:
            payload = literal_eval(data_string)
        except:
            return None
    if isinstance(payload, list) and len(payload) == 2:
        payload = {payload[0]: payload[1]}

    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=400, content={"message": "Invalid data sent, should be json"}
        )

    resp = Response(status_code=400)
    for device, list_or_dict in payload.items():
        if not isinstance(device, str):
            continue

        if isinstance(list_or_dict, list) and len(list_or_dict) == 2:
            datadict = {"time": list_or_dict[0], "data": list_or_dict[1]}
        elif isinstance(list_or_dict, dict):
            datadict = {k.lower(): v for k, v in list_or_dict.items()}
        else:
            return JSONResponse(
                status_code=400, content={"message": "Invalid device data sent, should be json"}
            )

        result = await post_data(location, device, datadict)
        if result.status_code == 204:
            resp = result
    return resp


@router.get("/{location}/{device}")
async def get_data(location: str, device: str):
    return r_conn.get("sensors", f".{location}.{device}")


@router.post("/{location}/{device}")
async def post_data(location: str, device: str, data: dict):
    time = data.get("time")
    payload = data.get("data")
    if time is None or payload is None:
        return JSONResponse(
            status_code=400,
            content={"message": "time and/or data, key is missing from device_key"},
        )
    data_dict = f._transform_to_dict(payload)
    if f._validate_time(r_conn, location, device, time):
        if data_dict is not None:
            with suppress(Exception):
                new_data = {}
                for k, v in data_dict.items():
                    value = f._test_adjust_value(location, k, v)
                    if value is None:
                        logging.warning(f"Sensors invalid value: {device}, {k}: {v}")
                        break
                    new_data[k] = value
                else:
                    f._set_json(r_conn, f".{location}.{device}.data", new_data)
                    f._set_json(r_conn, f".{location}.{device}.time", time)
                    f._set_json(r_conn, f".{location}.{device}.new", True)
                    return Response(status_code=204)
        else:
            logging.warning(f"Sensors data malformed: {device}, {str(data)[:20]}")
    else:
        logging.warning(f"Old data sent: {device}, {time[:20]}")
    return Response(status_code=400)


@router.post("/home/balcony/relay/status")
async def post_relay_status(data: List[int]):
    if not set(data).difference(set((0, 1))) and len(data) == 4:
        f._set_json(r_conn, ".home.balcony.relay.status", data)
    else:
        logging.warning("Status data malformed: " + str(data)[:26])
        return Response(status_code=400)
    return Response(status_code=204)


@router.get("/home/balcony/relay/status")
async def get_relay_status():
    with suppress(redis.exceptions.ResponseError):
        return r_conn.get("sensors", ".home.balcony.relay.status")
    return JSONResponse(status_code=503, content={"message": "Relay status redis data is missing"})


# Insert data to database
@router.post("/db")
async def insert_db(data: LocationSensorData, db: Session = Depends(get_db)):
    curr_time = datetime.utcnow()
    _crud.add_timestamp(db, _schemas.TimeStamp(time=curr_time))
    for location in data.__root__:
        if _crud.get_location(db, name=location) is None:
            _crud.add_location(db, name=location)
        for device in data.__root__[location].__root__:
            if _crud.get_device(db, name=device) is None:
                _crud.add_device(db, name=device)
            if data.__root__[location].__root__[device].new:
                for key, value in data.__root__[location].__root__[device].data.__root__.items():
                    if _crud.get_mtype(db, name=key) is None:
                        _crud.add_mtype(db, name=key)
                    _crud.add_measurement(
                        db,
                        _schemas.Measurements(
                            name=location,
                            device=_schemas.Device(name=device),
                            mtype=_schemas.MeasureType(name=key),
                            time=_schemas.TimeStamp(time=curr_time),
                            value=value,
                        ),
                    )
                f._set_json(r_conn, f".{location}.{device}.new", False)
    return Response(status_code=204)
