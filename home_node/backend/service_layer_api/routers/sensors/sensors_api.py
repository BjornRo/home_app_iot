import logging
from . import _func as f
from .. import MyRouterAPI
from contextlib import suppress
from main import r_conn, get_db
from datetime import datetime
from fastapi import Depends, HTTPException, Response
from typing import List, Dict
from sqlalchemy.orm import Session
from pydantic import BaseModel
from . import _crud, _schemas

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


@router.get("/{location}/{device}")
async def get_data(location: str, device: str):
    return r_conn.get("sensors", f".{location}.{device}")


@router.post("/{location}/{device}")
async def post_data(location: str, device: str, data: dict | list | int | float | str):
    data_dict = f._transform_to_dict(data)
    if data_dict is not None:
        new_data = {}
        for k, v in data_dict.items():
            value = f._test_value(location, k, v)
            if value is None:
                data_dict = None
                break
            new_data[k] = value
        else:
            f._set_json(r_conn, f".home.{device}.data", new_data)
            f._set_json(r_conn, f".home.{device}.time", datetime.utcnow().isoformat("T"))
            f._set_json(r_conn, f".home.{device}.new", True)
    if data_dict is None:
        logging.warning(f"Sensors data malformed: {device}, {str(data)[:15]}")
    return Response(status_code=204)


@router.post("/home/balcony/relay/status")
async def post_relay_status(data: List[int]):
    if not set(data).difference(set((0, 1))) and len(data) == 4:
        f._set_json(r_conn, ".home.balcony.relay.status", data)
    else:
        logging.warning("Status data malformed: " + str(data)[:26])
    return Response(status_code=204)


@router.get("/home/balcony/relay/status")
async def get_relay_status():
    return r_conn.get("sensors", ".home.balcony.relay.status")


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
