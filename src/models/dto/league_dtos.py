from pydantic import BaseModel, ConfigDict

from .player_dtos import Player


class LeagueRequest(BaseModel):
    league_name: str


class League(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    players: list[Player] = []
