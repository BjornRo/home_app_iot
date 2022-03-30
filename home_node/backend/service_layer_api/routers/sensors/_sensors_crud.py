from pymodules.schemas import sensors_db_schemas as dbschemas
from datetime import datetime
from db.db_models import Devices, DeviceMeasures, Locations, Measurements, MeasureTypes, TimeStamps
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def add_timestamp(session: AsyncSession, timestamp: datetime):
    time = TimeStamps(time=timestamp)
    session.add(time)
    await session.commit()
    return time


async def get_location(session: AsyncSession, name: str) -> Locations | None:
    stmt = (
        select(Locations).where(func.lower(Locations.name) == func.lower(name))
        # .options(selectinload(Locations.devices))
    )
    return (await session.execute(stmt)).scalar()


async def add_location(session: AsyncSession, name: str):
    location = Locations(name=name.lower())
    session.add(location)
    await session.commit()
    return location


async def delete_location(session: AsyncSession, loc: Locations):
    await session.delete(loc)
    await session.commit()
    return loc


async def get_device(session: AsyncSession, name: str) -> Devices | None:
    stmt = select(Devices).where(func.lower(Devices.name) == name.lower())
    return (await session.execute(stmt)).scalar()


async def add_device(session: AsyncSession, location: str, name: str) -> Devices:
    device = Devices(name=name.lower(), location_name=location.lower())
    session.add(device)
    await session.commit()
    return device


async def get_mtype(session: AsyncSession, name: str) -> MeasureTypes | None:
    stmt = select(MeasureTypes).where(func.lower(MeasureTypes.name) == name.lower())
    return (await session.execute(stmt)).scalar()


async def add_mtype(session: AsyncSession, name: str) -> MeasureTypes:
    measure_type = MeasureTypes(name=name.lower())
    session.add(measure_type)
    await session.commit()
    return measure_type


async def get_device_measures(session: AsyncSession, device_id: int):
    stmt = select(DeviceMeasures).where(DeviceMeasures.device_id == device_id)
    return (await session.execute(stmt)).scalar()


async def add_device_measures(session: AsyncSession, device_id: int, mtype: int):
    device_measure_type = DeviceMeasures(device_id=device_id, measure_type_id=mtype)
    session.add(device_measure_type)
    await session.commit()
    return device_measure_type


async def add_measurement(session: AsyncSession, measurement: dbschemas.Measurements):
    measurement_data = Measurements(
        device_id=measurement.device_id,
        measure_type_id=measurement.measure_type_id,
        time_id=measurement.time_id,
        value=measurement.value,
    )
    session.add(measurement_data)
    await session.commit()
    return measurement_data
