from pydantic import BaseModel
from datetime import datetime


# Blocklist stuff
class BlocklistBase(BaseModel):
    ip: str


class BlocklistCreate(BlocklistBase):
    ban_expire: datetime
    manual_ban: bool


class BlocklistUpdate(BlocklistBase):
    ban_expire: datetime
    attempt_counter: int


class Blocklist(BlocklistUpdate):
    id: int
    total_attempts: int
    manual_ban: bool

    class Config:
        orm_mode = True
