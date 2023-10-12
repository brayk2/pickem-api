from typing import Optional

from pydantic import BaseModel, ConfigDict


class Player(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None


class PlayerRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    email: str
