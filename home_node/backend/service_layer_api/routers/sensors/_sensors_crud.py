from . import _sensors_db_schemas as dbschemas
from db.db_models import Devices, DeviceMeasures, Locations, Measurements, MeasureTypes, TimeStamps
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession


async def add_timestamp(session: AsyncSession, timestamp: dbschemas.TimeStamp):
    time = TimeStamps(time=timestamp.time)
    session.add(time)
    await session.commit()
    return time


async def get_location(session: AsyncSession, name: str) -> Locations | None:
    stmt = select(Locations).where(func.lower(Locations.name) == func.lower(name))
    return (await session.execute(stmt)).scalar()


async def add_location(session: AsyncSession, name: str):
    location = Locations(name=name.lower())
    session.add(location)
    await session.commit()
    return location


async def get_device(session: AsyncSession, name: str) -> Devices | None:
    stmt = select(Devices).where(func.lower(Devices.name) == name.lower())
    return (await session.execute(stmt)).scalar()


async def add_device(session: AsyncSession, name: str) -> Devices:
    device = Devices(name=name.lower())
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


async def get_device_measures(session: AsyncSession, device: str, mtype: str):
    stmt = select(DeviceMeasures).where(
        and_(
            func.lower(DeviceMeasures.name) == device.lower(),
            func.lower(DeviceMeasures.mtype) == mtype.lower(),
        )
    )
    return (await session.execute(stmt)).scalar()


async def add_device_measures(session: AsyncSession, device: str, mtype: str):
    device_measure_type = DeviceMeasures(name=device.lower(), mtype=mtype.lower())
    session.add(device_measure_type)
    await session.commit()
    return device_measure_type


async def add_measurement(session: AsyncSession, measurement: dbschemas.Measurements):
    measurment_data = Measurements(
        location=measurement.name.lower(),
        device=measurement.device.name.lower(),
        mtype=measurement.mtype.name.lower(),
        time=measurement.time.time,
        value=measurement.value,
    )
    session.add(measurment_data)
    await session.commit()
    return measurment_data
