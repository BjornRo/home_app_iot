from pydantic import BaseModel
from datetime import datetime

class Location(BaseModel):
    name: str

class Device(BaseModel):
    id: int
    location_name: Location
    name: str

class MeasureType(BaseModel):
    id: int
    name: str

class DeviceMeasures(BaseModel):
    device_name: str
    measure_type_id: int

class TimeStamp(BaseModel):
    id: int
    time: datetime

class Measurements(BaseModel):
    device_id: int
    measure_type_id: int
    time_id: int
    value: float

    class Config:
        orm_mode = True
