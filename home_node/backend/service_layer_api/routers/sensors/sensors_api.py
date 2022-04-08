import logging
import redis
from . import _sensors_crud as crud, _func as f
from .. import MyRouterAPI
from contextlib import suppress
from datetime import datetime
from fastapi import Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from main import r_conn, get_session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Tuple
from pymodules.schemas import sensors_db_schemas as dbschemas
from pymodules.schemas.sensors_schemas import *

# Settings
PREFIX = "/sensors"
TAGS = ["sensors_api"]


# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router

# Routing
@router.get("/", response_model=LocationSensorData)
async def get_sensor_data():
    data: dict | None = r_conn.get("sensors")
    if data is None:
        raise HTTPException(status_code=404, detail="Sensor data is missing")
    return data


# TODO Remove
@router.get("/clear_redis")
async def psd():
    r_conn.set("sensors", ".", {})


@router.post("/{location}", status_code=204)
async def post_location_data(location: str, data: RawLocationData):
    n_valid = 0
    for device, list_or_dict in data.items():
        # Allow atleast one device to update its data.
        if 200 <= (await post_data(location, device, list_or_dict)).status_code <= 204:
            n_valid += 1
    if not n_valid:
        return JSONResponse(status_code=422, content="All data sent was invalid")
    elif n_valid == len(data.dict()):
        return Response(status_code=204)
    else:
        return JSONResponse(status_code=422, content="Partial data sent was invalid")


@router.get("/{location}/{device}", response_model=DataPackage)
async def get_data(location: str, device: str):
    return r_conn.get("sensors", f".{location}.{device}")


@router.post("/{location}/{device}", status_code=204)
async def post_data(
    location: str,
    device: str,
    data: RawDeviceData | Tuple[datetime, RawListData | MeasurementData],
):
    if isinstance(data, RawDeviceData):
        time, payload = data.time, data.data
    else:
        time, payload = data

    location, device = location.lower(), device.lower()

    data_model = f.transform_to_model(payload)
    if data_model is None:
        logging.warning(f"Empty data sent from: {location}, {device}")
        return JSONResponse(status_code=422, content="Data is empty")

    if f.validate_time(r_conn, location, device, time):
        for k, v in data_model.items():
            if not f.test_value(k, v):
                logging.warning(f"Sensors invalid value: {device}, {k}: {v}")
                break
        else:
            f.set_json(r_conn, f".{location}.{device}.data", data_model.dict())
            f.set_json(r_conn, f".{location}.{device}.time", time.isoformat())
            f.set_json(r_conn, f".{location}.{device}.new", True)
            return Response(status_code=204)
    else:
        logging.warning(f"Old data sent: {device}, {time.isoformat()}")
    return JSONResponse(status_code=422, content="Invalid data")


@router.get("/home/balcony/relay/status", response_model=RelayStatus)
async def get_relay_status():
    with suppress(redis.exceptions.ResponseError):
        return r_conn.get("sensors", ".home.balcony.relay.status")
    raise HTTPException(status_code=503, detail="Relay status redis data is missing")


@router.post("/home/balcony/relay/status", status_code=204)
async def post_relay_status(data: RelayStatus):
    f.set_json(r_conn, ".home.balcony.relay.status", data.dict())
    return Response(status_code=204)


# Insert data to database
@router.post("/", status_code=204)
async def insert_db(location_data: LocationSensorData, session: AsyncSession = Depends(get_session)):
    curr_time = datetime.utcnow()
    time_id = (await crud.add_timestamp(session, curr_time)).id
    for location, devicedata in location_data.items():
        if await crud.get_location(session, name=location) is None:
            await crud.add_location(session, name=location)
        for device, data in devicedata.items():
            db_dev = await crud.get_device(session, name=device)
            if db_dev is None:
                db_dev = await crud.add_device(session, name=device, location=location)
            if not data.new:
                continue
            for mtype, value in data.data.items():
                db_mtype = await crud.get_mtype(session, name=mtype)
                if db_mtype is None:
                    db_mtype = await crud.add_mtype(session, name=mtype)
                if await crud.get_device_measures(session, db_dev.id) is None:  # type:ignore
                    await crud.add_device_measures(session, db_dev.id, db_mtype.id)  # type:ignore
                await crud.add_measurement(
                    session,
                    dbschemas.Measurements(
                        device_id=db_dev.id,  # type:ignore
                        measure_type_id=db_mtype.id,  # type:ignore
                        time_id=time_id,  # type:ignore
                        value=value,
                    ),
                )
            f.set_json(r_conn, f".{location}.{device}.new", False)
    return Response(status_code=204)
