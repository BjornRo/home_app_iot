from pydantic import BaseModel
from datetime import datetime

class Location(BaseModel):
    name: str

class Device(BaseModel):
    name: str

class MeasureType(BaseModel):
    name: str

class DeviceMeasures(Device):
    mtype: MeasureType

class TimeStamp(BaseModel):
    time: datetime

class Measurements(Location):
    device: Device
    mtype: MeasureType
    time: TimeStamp
    value: float

