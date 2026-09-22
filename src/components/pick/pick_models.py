from datetime import datetime

from pydantic import conlist, Field
from strenum import StrEnum

from src.components.results.results_models import MatchupDto, TeamDto, PickDto
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


class AdminSubmitPicksRequestDto(SubmitPicksRequestDto):
    """
    One player's whole week, written by somebody who is not that player.

    Deliberately stricter than the player's own submission, which accepts a
    partial slate so picks can be saved and come back to. There is no
    half-finished admin edit: an override either leaves a complete, well-formed
    week behind or it is rejected. `PickService._validate_slate` enforces the
    part the length cannot -- five *distinct* games at five distinct
    confidences.
    """

    picks: conlist(item_type=PickRequest, min_length=5, max_length=5)
    # Free text, required. The audit row is worth little without it, and a
    # default would be filled in by the client and never read.
    reason: str = Field(min_length=1, max_length=500)
    # A second, explicit act for the part that is actually irreversible.
    # Without it an override behaves exactly like the player's own submission:
    # it may fix an un-started week, and kickoff still refuses everything else.
    override_locked: bool = Field(default=False)


class PickOverrideSlotDto(BaseDto):
    """
    One pick inside a recorded slate.

    The ids are what the audit row actually stores; the names are resolved when
    it is read. Storing the names would have frozen them, which sounds like the
    safer choice but is not -- a team that relocates would leave the log
    disagreeing with every other screen in the app about who it is. Storing the
    ids and resolving late means the record is stable and the display is
    current.
    """

    game_id: int
    team_id: int
    team_name: str | None = None
    team_abbreviation: str | None = None
    spread_value: float
    confidence: int
    status: str | None = None


class PickOverrideDto(BaseDto):
    """One entry in the override log."""

    id: int
    username: str
    actor: str
    week: int
    reason: str
    locks_bypassed: bool
    before: list[PickOverrideSlotDto]
    after: list[PickOverrideSlotDto]
    created_at: datetime


class RevertOverrideRequestDto(BaseDto):
    """
    Undoing an override.

    A reason is optional here, unlike the override itself: "put it back the way
    it was" is self-explaining in a way that "change it to this" is not, and
    the generated reason already names the entry being undone.
    """

    reason: str | None = Field(default=None, max_length=500)
