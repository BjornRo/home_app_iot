from datetime import datetime
from pydantic import BaseModel, root_validator
from typing import Tuple

# region
class DictModel(BaseModel):
    # Just so you can use this.
    def items(self):
        return self.__root__.items()  # type:ignore

    # https://github.com/tiangolo/fastapi/issues/911
    # This is a temp fix until https://github.com/tiangolo/fastapi/pull/4428 is approved
    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        if "__root__" in d:
            d = d["__root__"]
        return d

    def __iter__(self):
        return iter(self.__root__)  # type:ignore

    def __getitem__(self, item):
        return self.__root__[item]  # type:ignore

    def __bool__(self):
        return bool(self.__root__)  # type:ignore

    @root_validator
    def lower_case(cls, values):
        return {"__root__": {k.lower(): v for k, v in values["__root__"].items()}}


class LowerCaseNonRootModel(BaseModel):
    @root_validator
    def lower_case(cls, values):
        return {k.lower(): v for k, v in values.items()}  # endregion


class MeasurementData(DictModel):
    __root__: dict[str, float]


class RawListData(BaseModel):
    __root__: list[float]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, index):
        return self.__root__[index]

    def __bool__(self):
        return bool(self.__root__)


class RawDeviceData(LowerCaseNonRootModel):
    time: datetime
    data: RawListData | MeasurementData


class RawLocationData(DictModel):
    __root__: dict[str, RawDeviceData | Tuple[datetime, RawListData | MeasurementData]]


# Redis model.
class DataPackage(LowerCaseNonRootModel):
    data: MeasurementData
    time: datetime
    new: bool


class DeviceData(DictModel):
    __root__: dict[str, DataPackage]


class LocationSensorData(DictModel):
    __root__: dict[str, DeviceData]


class RelayStatus(BaseModel):
    light_full: bool
    light_dim: bool
    heater: bool
    unused: bool