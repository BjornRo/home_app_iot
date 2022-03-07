import logging
from datetime import datetime
from pydantic import BaseModel, root_validator
from typing import Tuple


# ({"pizw": {"time": "2022-03-06T22:33:53.631231", "data": {"temperature": -99}}})
# ({"pizw": ["2022-03-06T22:33:53.631231", {"temperature": -99}]})


# Data expected as unaltered as possible from devices
class MeasurementData(BaseModel):
    __root__: dict[str, float | int]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    def __bool__(self):
        return bool(self.__root__)

    @root_validator
    def lower_case(cls, values):
        return {"__root__": {k.lower(): v for k, v in values["__root__"].items()}}


class RawShallowList(BaseModel):
    __root__: list[float | int]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, index):
        return self.__root__[index]

    def __bool__(self):
        return bool(self.__root__)


class RawTupleList(BaseModel):
    __root__: list[Tuple[str, float | int]]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, index):
        return self.__root__[index]

    def __bool__(self):
        return bool(self.__root__)

    @root_validator
    def lower_case(cls, values):
        if values:
            items = values["__root__"]
            if items and isinstance(items[0], list | tuple):
                return {"__root__": [(k[0].lower(), k[1]) for k in items if k]}
        return values


class RawListData(BaseModel):
    __root__: RawShallowList | RawTupleList

    def __iter__(self):
        return iter(self.__root__)

    def __bool__(self):
        return bool(self.__root__)


class RawDeviceData(BaseModel):
    time: datetime | None
    data: RawListData | MeasurementData

    @root_validator
    def lower_case(cls, values):
        return {k.lower(): v for k, v in values.items()}


class RawLocationData(BaseModel):
    __root__: dict[str, RawDeviceData | Tuple[datetime, RawListData | MeasurementData]]

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


class LocationSensorData(BaseModel):
    __root__: dict[str, DeviceData]
