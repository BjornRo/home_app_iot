from datetime import datetime
from pydantic import BaseModel


class Error(BaseModel):
    device_name: str
    time: datetime
    log_level: str
    msg: str

    class Config:
        orm_mode = True
