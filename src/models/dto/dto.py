from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Spread(BaseModel):
    id: int
    bookmaker: str
    home_point_spread: float
    away_point_spread: float
    home_spread_price: float
    away_spread_price: float


class Results(BaseModel):
    id: int
    completed: bool = False
    home_score: int = 0
    away_score: int = 0


class Team(BaseModel):
    id: int
    name: Optional[str] = None
    thumbnail: Optional[str] = None


class Game(BaseModel):
    id: int
    home_team: Team
    away_team: Team
    spreads: list[Spread]
    results: Optional[Results] = None
    start_time: Optional[datetime] = None
