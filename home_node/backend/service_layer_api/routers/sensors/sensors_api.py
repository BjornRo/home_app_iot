import logging
import redis
from . import _sensors_db_schemas as dbschemas, _sensors_crud as crud, _func as f
from ._sensors_schemas import *
from .. import MyRouterAPI
from contextlib import suppress
from datetime import datetime
from fastapi import Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from main import r_conn, get_db
from sqlalchemy.orm import Session
from typing import Tuple

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


# Routing
@router.get("/data")
async def get_sensor_data():
    data: dict | None = r_conn.get("sensors")
    if data:
        with suppress(KeyError):
            del data["home"]["balcony"]["relay"]
        return data
    raise HTTPException(status_code=404)


@router.get("/clear_redis")
async def psd():
    r_conn.set("sensors", ".", {})


@router.post("/{location}")
async def post_location_data(location: str, data: RawLocationData):
    resp = Response(status_code=400)
    for device, list_or_dict in data.__root__.items():
        result = await post_data(location, device, list_or_dict)
        # Allow atleast one device to update its data.
        if result.status_code == 204:
            resp = result
    return resp


@router.get("/{location}/{device}")
async def get_data(location: str, device: str):
    return r_conn.get("sensors", f".{location}.{device}")


@router.post("/{location}/{device}")
async def post_data(
    location: str,
    device: str,
    data: RawDeviceData | Tuple[datetime, RawListData | MeasurementData],
):
    if isinstance(data, RawDeviceData):
        time, payload = data.time, data.data
    else:
        time, payload = data

    if time is None:
        return JSONResponse(status_code=400, content={"message": "time is missing"})

    location, device = location.lower(), device.lower()

    data_dict = f._transform_to_dict(payload)

    if f._validate_time(r_conn, location, device, time):
        if data_dict is not None:
            with suppress(Exception):
                new_data = {}
                for k, v in data_dict.__root__.items():
                    value = f._test_value(location, k, v)
                    if value is None:
                        logging.warning(f"Sensors invalid value: {device}, {k}: {v}")
                        break
                    new_data[k] = value
                else:
                    f._set_json(r_conn, f".{location}.{device}.data", new_data)
                    f._set_json(r_conn, f".{location}.{device}.time", time.isoformat())
                    f._set_json(r_conn, f".{location}.{device}.new", True)
                    return Response(status_code=204)
        else:
            logging.warning(f"Sensors data malformed: {device}, {str(data)[:20]}")
    else:
        logging.warning(f"Old data sent: {device}, {time.isoformat()}")
    return Response(status_code=400)


@router.post("/home/balcony/relay/status")
async def post_relay_status(data: list[int]):
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
    crud.add_timestamp(db, dbschemas.TimeStamp(time=curr_time))
    for location in data.__root__:
        if crud.get_location(db, name=location) is None:
            crud.add_location(db, name=location)
        for device in data.__root__[location].__root__:  # TODO Add deviceMeasures somewhere...
            if crud.get_device(db, name=device) is None:
                crud.add_device(db, name=device)
            if data.__root__[location].__root__[device].new:
                for key, value in data.__root__[location].__root__[device].data.__root__.items():
                    if crud.get_mtype(db, name=key) is None:
                        crud.add_mtype(db, name=key)
                    crud.add_measurement(
                        db,
                        dbschemas.Measurements(
                            name=location,
                            device=dbschemas.Device(name=device),
                            mtype=dbschemas.MeasureType(name=key),
                            time=dbschemas.TimeStamp(time=curr_time),
                            value=value,
                        ),
                    )
                f._set_json(r_conn, f".{location}.{device}.new", False)
    return Response(status_code=204)
