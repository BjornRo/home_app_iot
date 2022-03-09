from datetime import datetime
from pydantic import BaseModel, root_validator
from typing import Tuple


class MeasurementData(BaseModel):
    __root__: dict[str, float]

    def items(self):
        return self.__root__.items()

    def dict(self):
        return self.__root__

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    def __bool__(self):
        return bool(self.__root__)

    @root_validator
    def lower_case(cls, values):
        return {"__root__": {k.lower(): v for k, v in values["__root__"].items()}}


class RawListData(BaseModel):
    __root__: list[float]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, index):
        return self.__root__[index]

    def __bool__(self):
        return bool(self.__root__)


class RawDeviceData(BaseModel):
    time: datetime
    data: RawListData | MeasurementData

    @root_validator
    def lower_case(cls, values):
        return {k.lower(): v for k, v in values.items()}


class RawLocationData(BaseModel):
    __root__: dict[str, RawDeviceData | Tuple[datetime, RawListData | MeasurementData]]

    def items(self):
        return self.__root__.items()

    def dict(self):
        return self.__root__

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    def __bool__(self):
        return bool(self.__root__)

    @root_validator
    def lower_case(cls, values):
        return {"__root__": {k.lower(): v for k, v in values["__root__"].items()}}


# Redis models how the data is stored in redis
class Data(BaseModel):
    data: MeasurementData
    time: datetime
    new: bool

    @root_validator
    def lower_case(cls, values):
        return {k.lower(): v for k, v in values.items()}


class DeviceData(BaseModel):
    __root__: dict[str, Data]

    def items(self):
        return self.__root__.items()

    def __getitem__(self, item):
        return self.__root__[item]

    def __iter__(self):
        return iter(self.__root__)


class LocationSensorData(BaseModel):
    __root__: dict[str, DeviceData]

    def items(self):
        return self.__root__.items()

    def __getitem__(self, item):
        return self.__root__[item]

    def __iter__(self):
        return iter(self.__root__)
