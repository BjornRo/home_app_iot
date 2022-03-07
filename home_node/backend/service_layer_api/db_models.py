from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime, Sequence
from sqlalchemy.orm import relationship

from db import Base

# Users
class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, Sequence("user_id_seq"), primary_key=True)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    date_added = Column(DateTime, nullable=False)


class UserDescription(Base):
    __tablename__ = "userdescription"

    userid = Column(Integer, ForeignKey("users.id"), primary_key=True)
    text = Column(String, nullable=False)


# Blocklist for misc uses.
class Blocklist(Base):
    __tablename__ = "blocklist"

    id = Column(Integer, Sequence("blocklist_id_seq"), primary_key=True)
    ip = Column(String, nullable=False, unique=True)
    ban_first = Column(DateTime, nullable=False)
    ban_expire = Column(DateTime, nullable=False)
    total_attempts = Column(Integer, nullable=False)
    attempt_counter = Column(Integer, nullable=False)
    manual_ban = Column(Boolean, nullable=False)


# Sensors tables
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
