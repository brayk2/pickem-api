from enum import StrEnum

from pydantic import Field

from src.models.base_models import BaseDto


class LeagueRole(StrEnum):
    Member = "MEMBER"
    Commissioner = "COMMISSIONER"


class LeagueDto(BaseDto):
    id: int
    name: str
    description: str | None = None


class CreateLeagueRequest(BaseDto):
    name: str
    description: str | None = None


class LeagueSeasonDto(BaseDto):
    id: int
    league_id: int = Field(alias="leagueId")
    year: int
    settings: dict = Field(default_factory=dict)


class LeagueMemberDto(BaseDto):
    user_id: int = Field(alias="userId")
    username: str
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    role: LeagueRole = LeagueRole.Member


class AddLeagueMemberRequest(BaseDto):
    username: str
    role: LeagueRole = LeagueRole.Member


class LeagueRosterDto(BaseDto):
    league_id: int = Field(alias="leagueId")
    year: int
    members: list[LeagueMemberDto] = Field(default_factory=list)
