from pydantic import conlist, Field
from strenum import StrEnum

from src.components.results.results_dto import MatchupDto, TeamDto, PickDto
from src.models.base_models import BaseDto


class PickStatus(StrEnum):
    New = "NEW"
    Saved = "SAVED"
    Submitted = "SUBMITTED"
    Locked = "LOCKED"


class PickRequest(BaseDto):
    game_id: int = Field(alias="gameId")
    team_id: int = Field(alias="teamId")
    spread_value: float = Field(alias="spreadValue")
    confidence: int
    status: PickStatus = Field(default=PickStatus.New)


class UserPicksDto(BaseDto):
    picks: list[PickDto] = []  # Allow for an empty list of picks
    status: PickStatus  # Overall status of the picks


class SubmitPicksRequestDto(BaseDto):
    year: int
    week: int
    picks: conlist(item_type=PickRequest, min_length=1, max_length=5)
    status: PickStatus = Field(default=PickStatus.New)  # Default status


class SubmitPicksResponseDto(BaseDto):
    status: str
    detail: str
