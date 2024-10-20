from datetime import time, date

from pydantic import Field, field_validator, ValidationError
from typing import List, Literal

from src.models.base_models import BaseDto


class TeamDto(BaseDto):
    team_id: int
    team_name: str
    team_city: str
    abbreviation: str | None = None
    thumbnail: str
    primary_color: str | None = None
    secondary_color: str | None = None


class GameResultDto(BaseDto):
    home_team_id: int = Field(alias="homeTeamId")
    home_team_name: str = Field(alias="homeTeamName")
    home_team_city: str = Field(alias="homeTeamCity")
    home_team_score: int = Field(alias="homeTeamScore")
    home_team_thumbnail: str | None = Field(alias="homeTeamThumbnail", default=None)
    away_team_id: int = Field(alias="awayTeamId")
    away_team_name: str = Field(alias="awayTeamName")
    away_team_city: str = Field(alias="awayTeamCity")
    away_team_score: int = Field(alias="awayTeamScore")
    away_team_thumbnail: str | None = Field(alias="awayTeamThumbnail", default=None)


class GameDto(BaseDto):
    game_id: int = Field(alias="gameId")
    home_team: TeamDto = Field(alias="homeTeam")
    away_team: TeamDto = Field(alias="awayTeam")
    result: GameResultDto | None = Field(alias="result", default=None)
    week: int | None = Field(default=None)
    year: int | None = Field(default=None)


class MatchupDto(BaseDto):
    game_id: int
    home_team: TeamDto
    away_team: TeamDto
    start_time: time | None = None
    start_date: date | None = None

    lines: dict[str, str | None] | None = Field(default_factory=dict)
    ats: dict[str, str] | None = Field(default_factory=dict)
    record: dict[str, str] | None = Field(default_factory=dict)
    results: dict[str, int] | None = Field(default=None)
    home_record: dict[str, str] | None = Field(default_factory=dict)
    away_record: dict[str, str] | None = Field(default_factory=dict)

    @field_validator("results", mode="before")
    @classmethod
    def validate_results(cls, val) -> dict[str, int] | None:
        if not val:
            return None

        if not isinstance(val, dict):
            raise ValidationError("results must be a dict")

        if not len(val.values()):
            raise ValidationError("must have exactly two results")

        if not all(val.values()):
            # set to none if scores are none
            return None

        return val


class PickDto(BaseDto):
    id: int
    team: TeamDto = Field(alias="team")
    confidence: int
    spread_value: float = Field(alias="line")
    status: str
    game: MatchupDto | None = Field(alias="game", default=None)
    score: float = Field(default=0.0)
    pick_status: Literal["COVERED", "FAILED", "PUSHED", "UNKNOWN"] | None = Field(
        default=None
    )


class UserPickResultsDto(BaseDto):
    username: str
    picks: List[PickDto]
    total_score: float = Field(default=0.0)
    rank: int | None = Field(default=None)


class LeaguePickResultsDto(BaseDto):
    username: str
    total_score: int
    rank: int


class ResultsResponseDto(BaseDto):
    year: int
    week: int
    user_results: List[UserPickResultsDto] = Field(alias="userResults")
    league_results: List[LeaguePickResultsDto] = Field(alias="leagueResults")
    nfl_game_results: List[GameResultDto] = Field(alias="nflGameResults")


class WeekResultsDto(BaseDto):
    week: int
    results: List[UserPickResultsDto]
