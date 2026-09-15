from typing import Literal, List

from pydantic import Field

from src.components.results.results_dto import TeamDto
from src.models.base_models import BaseDto

# A side's outcome is normally one of the three grades. MIXED covers the case
# where the line moved between picks and the players who took the same side
# ended up on opposite sides of the number.
PickOutcome = Literal["COVERED", "FAILED", "PUSHED", "MIXED", "UNKNOWN"]


class SideBreakdownDto(BaseDto):
    """How the league treated one side of one game."""

    game_id: int
    team: TeamDto
    opponent: TeamDto
    line: float
    result: PickOutcome
    # Signed points this side beat its line by; negative means it fell short.
    margin: float
    pick_count: int
    pick_share: float = Field(description="Share of this game's picks, 0..1")
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0
    average_confidence: float | None = None
    average_points: float | None = None
    total_points: float = 0.0


class GameBreakdownDto(BaseDto):
    """One game, and how the league split on it."""

    game_id: int
    home_team: TeamDto
    away_team: TeamDto
    home_score: int
    away_score: int
    home: SideBreakdownDto
    away: SideBreakdownDto
    pick_count: int
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0
    hit_rate: float | None = None
    average_points: float | None = None
    is_unanimous: bool = False


class NotablePickDto(BaseDto):
    """One side of one game, singled out as a superlative."""

    game_id: int
    team: TeamDto
    opponent: TeamDto
    line: float
    result: PickOutcome
    pick_count: int
    pick_share: float
    covered_count: int = 0
    failed_count: int = 0
    average_points: float | None = None


class ConfidenceBreakdownDto(BaseDto):
    """How the league did at one confidence level."""

    confidence: int
    pick_count: int
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0
    hit_rate: float | None = None
    average_points: float | None = None


class PlayerScoreDto(BaseDto):
    username: str
    score: float
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0


class SoloHitDto(BaseDto):
    """A player who was the only one on a side, and was right."""

    username: str
    game_id: int
    team: TeamDto
    opponent: TeamDto
    line: float
    confidence: int
    points: float


class PlayerConvictionDto(BaseDto):
    """
    Where a player's confidence landed.

    `points_per_hit` is the average confidence of the picks they got right. Six
    points off three correct picks is a 2.0; five points off a single correct
    pick is a 5.0 -- the same week's work, but the second player put their
    weight on the one that came in.
    """

    username: str
    score: float
    covered_count: int
    points_per_hit: float


class MarginPickDto(BaseDto):
    """A pick decided by almost nothing, either way."""

    username: str
    game_id: int
    team: TeamDto
    opponent: TeamDto
    line: float
    confidence: int
    result: PickOutcome
    margin: float
    points: float


class WeekSuperlativesDto(BaseDto):
    best_score: PlayerScoreDto | None = None
    worst_score: PlayerScoreDto | None = None
    best_conviction: PlayerConvictionDto | None = None
    misplaced_conviction: PlayerConvictionDto | None = None
    solo_hits: List[SoloHitDto] = Field(default_factory=list)
    photo_finishes: List[MarginPickDto] = Field(default_factory=list)


class WeekStatsDto(BaseDto):
    """
    End-of-week statistics for one league.

    Only published once the week is complete: a "most missed pick" computed on
    Sunday evening is a different pick by Tuesday, and a leaderboard that keeps
    rewriting its own history is worse than no leaderboard. When `completed` is
    false every other field is empty and callers should render nothing.
    """

    year: int
    week: int
    completed: bool
    player_count: int = 0
    pick_count: int = 0
    game_count: int = 0
    average_score: float | None = None
    median_score: float | None = None
    hit_rate: float | None = None
    most_popular_pick: NotablePickDto | None = None
    most_correct_pick: NotablePickDto | None = None
    most_missed_pick: NotablePickDto | None = None
    unanimous_picks: List[NotablePickDto] = Field(default_factory=list)
    confidence_breakdown: List[ConfidenceBreakdownDto] = Field(default_factory=list)
    games: List[GameBreakdownDto] = Field(default_factory=list)
    superlatives: WeekSuperlativesDto = Field(default_factory=WeekSuperlativesDto)
