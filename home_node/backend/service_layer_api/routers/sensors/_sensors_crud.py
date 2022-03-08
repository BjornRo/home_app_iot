from . import _sensors_db_schemas as dbschemas
from main import db_models as models
from sqlalchemy.orm import Session


def add_timestamp(db: Session, timestamp: dbschemas.TimeStamp):
    time = models.TimeStamps(time=timestamp.time)
    db.add(time)
    db.commit()
    db.refresh(time)
    return time


def get_location(db: Session, name: str):
    return db.query(models.Locations).filter(models.Locations.name == name).first()


def add_location(db: Session, name: str):
    location = models.Locations(name=name)
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def get_device(db: Session, name: str):
    return db.query(models.Devices).filter(models.Devices.name == name).first()


def add_device(db: Session, name: str):
    device = models.Devices(name=name)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def get_mtype(db: Session, name: str):
    return db.query(models.MeasureTypes).filter(models.MeasureTypes.name == name).first()


def add_mtype(db: Session, name: str):
    measure_type = models.MeasureTypes(name=name)
    db.add(measure_type)
    db.commit()
    db.refresh(measure_type)
    return measure_type


def get_device_measures(db: Session, device: str, mtype: str):
    return (
        db.query(models.DeviceMeasures)
        .filter(models.DeviceMeasures.name == device, models.DeviceMeasures.mtype == mtype)
        .first()
    )


def add_device_measures(db: Session, device: str, mtype: str):
    device_measure_type = models.DeviceMeasures(name=device, mtype=mtype)
    db.add(device_measure_type)
    db.commit()
    db.refresh(device_measure_type)
    return device_measure_type


def add_measurement(db: Session, measurement: dbschemas.Measurements):
    measurment_data = models.Measurements(
        location=measurement.name,
        device=measurement.device.name,
        mtype=measurement.mtype.name,
        time=measurement.time.time,
        value=measurement.value,
    )
    db.add(measurment_data)
    db.commit()
    db.refresh(measurment_data)
    return measurment_data
