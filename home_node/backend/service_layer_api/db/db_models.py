from db.db_config import Base
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime, Sequence, null
from sqlalchemy.orm import relationship

# Users
class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, Sequence("user_id_seq"), primary_key=True)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    date_added = Column(DateTime, nullable=False)

    description = relationship(
        "UserDescription", back_populates="user", cascade="all, delete", uselist=False
    )


class UserDescription(Base):
    __tablename__ = "userdescription"

    userid = Column(Integer, ForeignKey("users.id"), primary_key=True)
    text = Column(String, nullable=False)

    user = relationship("Users", back_populates="description")


# TODO remove this table.
# I don't want to store passwords in a separate file during development.
class UserPasswordCleartext(Base):
    __tablename__ = "userpasswordclear"

    userid = Column(Integer, ForeignKey("users.id"), primary_key=True)
    clear_password = Column(String, nullable=False)


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


"""
SQL Query to get original stuff back.

SELECT t2.location_name, t2.name, t4.name, t3.time, t1.value
FROM measurements t1
JOIN devices t2 on t1.device_id = t2.id
JOIN timestamps t3 on t1.time_id = t3.id
JOIN measure_types t4 on t4.id = t1.measure_type_id
WHERE t2.location_name = 'home'
;

"""


class Locations(Base):
    __tablename__ = "locations"

    name = Column(String, primary_key=True)

    devices = relationship("Devices", back_populates="location", cascade="all, delete")


class Devices(Base):
    __tablename__ = "devices"

    id = Column(Integer, Sequence("device_id"), primary_key=True)
    location_name = Column(String, ForeignKey("locations.name"))
    name = Column(String, nullable=False, unique=True)

    location = relationship("Locations", back_populates="devices")
    device_measures = relationship("DeviceMeasures", back_populates="device", cascade="all, delete")
    measurements = relationship("Measurements", back_populates="device", cascade="all, delete")


class MeasureTypes(Base):
    __tablename__ = "measure_types"

    id = Column(Integer, Sequence("measure_type_id"), primary_key=True)
    name = Column(String, nullable=False, unique=True)


class DeviceMeasures(Base):
    __tablename__ = "device_measures"

    device_id = Column(Integer, ForeignKey("devices.id"), primary_key=True)
    measure_type_id = Column(Integer, ForeignKey("measure_types.id"), primary_key=True)

    device = relationship("Devices", back_populates="device_measures")


class TimeStamps(Base):
    __tablename__ = "timestamps"

    id = Column(Integer, Sequence("timestamp_id"), primary_key=True)
    time = Column(DateTime, nullable=False, unique=True)

    measurements = relationship("Measurements", back_populates="timestamp", cascade="all, delete")


class Measurements(Base):
    __tablename__ = "measurements"

    device_id = Column(Integer, ForeignKey("devices.id"), primary_key=True)
    measure_type_id = Column(Integer, ForeignKey("measure_types.id"), primary_key=True)
    time_id = Column(Integer, ForeignKey("timestamps.id"), primary_key=True)
    value = Column(Float, nullable=False)

    device = relationship("Devices", back_populates="measurements")
    timestamp = relationship("TimeStamps", back_populates="measurements")
