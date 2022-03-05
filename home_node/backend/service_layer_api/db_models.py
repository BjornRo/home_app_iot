from unicodedata import name
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime
from sqlalchemy.orm import relationship

from db import Base


class Locations(Base):
    __tablename__ = "locations"

    name = Column(String, primary_key=True)


class Devices(Base):
    __tablename__ = "devices"

    name = Column(String, primary_key=True)


class MeasureTypes(Base):
    __tablename__ = "measureTypes"

    name = Column(String, primary_key=True)


class DeviceMeasures(Base):
    __tablename__ = "deviceMeasures"

    name = Column(String, ForeignKey("devices.name"), primary_key=True)
    mtype = Column(String, ForeignKey("measureTypes.name"), primary_key=True)


class TimeStamps(Base):
    __tablename__ = "timestamps"

    time = Column(DateTime, primary_key=True)


class Measurements(Base):
    __tablename__ = "measurements"

    location = Column(String, ForeignKey("locations.name"), primary_key=True)
    device = Column(String, ForeignKey("devices.name"), primary_key=True)
    mtype = Column(String, ForeignKey("measureTypes.name"), primary_key=True)
    time = Column(String, ForeignKey("timestamps.time"), primary_key=True)
    value = Column(Float)
