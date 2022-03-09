import logging
import redis
from . import _sensors_db_schemas as dbschemas, _sensors_crud as crud, _func as f
from ._sensors_schemas import *
from .. import MyRouterAPI
from contextlib import suppress
from datetime import datetime
from fastapi import Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from main import r_conn, get_session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Tuple

# Settings
PREFIX = "/sensors"
TAGS = ["sensors_api"]


# To route the routings down the document.
router = MyRouterAPI(prefix=PREFIX, tags=TAGS).router


# Routing
@router.get("/")
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

    data_dict = f.transform_to_dict(payload)

    if f.validate_time(r_conn, location, device, time):
        if data_dict is not None:
            with suppress(Exception):
                new_data = {}
                for k, v in data_dict.__root__.items():
                    value = f.test_value(k, v)
                    if value is None:
                        logging.warning(f"Sensors invalid value: {device}, {k}: {v}")
                        break
                    new_data[k] = value
                else:
                    f.set_json(r_conn, f".{location}.{device}.data", new_data)
                    f.set_json(r_conn, f".{location}.{device}.time", time.isoformat())
                    f.set_json(r_conn, f".{location}.{device}.new", True)
                    return Response(status_code=204)
        else:
            logging.warning(f"Sensors data malformed: {device}, {str(data)[:20]}")
    else:
        logging.warning(f"Old data sent: {device}, {time.isoformat()}")
    return Response(status_code=400)


@router.post("/home/balcony/relay/status")
async def post_relay_status(data: list[int]):
    if not set(data).difference(set((0, 1))) and len(data) == 4:
        f.set_json(r_conn, ".home.balcony.relay.status", data)
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
@router.post("/")
async def insert_db(location_data: LocationSensorData, session: AsyncSession = Depends(get_session)):
    curr_time = datetime.utcnow()
    await crud.add_timestamp(session, dbschemas.TimeStamp(time=curr_time))
    for location, devicedata in location_data.items():
        if await crud.get_location(session, name=location) is None:
            await crud.add_location(session, name=location)
        for device, data in devicedata.items():
            if await crud.get_device(session, name=device) is None:
                await crud.add_device(session, name=device)
            if not data.new:
                continue
            for mtype, value in data.data.items():
                if await crud.get_mtype(session, name=mtype) is None:
                    await crud.add_mtype(session, name=mtype)
                if await crud.get_device_measures(session, device, mtype) is None:
                    await crud.add_device_measures(session, device, mtype)
                await crud.add_measurement(
                    session,
                    dbschemas.Measurements(
                        name=location,
                        device=dbschemas.Device(name=device),
                        mtype=dbschemas.MeasureType(name=mtype),
                        time=dbschemas.TimeStamp(time=curr_time),
                        value=value,
                    ),
                )
            f.set_json(r_conn, f".{location}.{device}.new", False)
    return Response(status_code=204)
