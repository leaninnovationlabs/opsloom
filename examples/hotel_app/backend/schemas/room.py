from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from typing import Literal

# models a hotel room 
class RoomSchema(BaseModel):
    room_id: int
    room_type: Literal["single", "double", "suite"]
    rate: float
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True