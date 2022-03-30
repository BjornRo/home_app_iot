from pydantic import BaseModel
from typing import Any

class MQTTPacket(BaseModel):
    topic: str
    payload: dict[str, Any] | list[int]
    retain: bool
