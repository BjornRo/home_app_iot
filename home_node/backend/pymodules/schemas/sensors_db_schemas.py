from pydantic import BaseModel
from datetime import datetime

class Locations(BaseModel):
    name: str

class Devices(BaseModel):
    id: int
    location_name: Locations
    name: str

    class Config:
        orm_mode = True


class MeasureTypes(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

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
