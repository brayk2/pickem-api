from typing import Literal, List

from pydantic import Field

from src.components.results.results_models import TeamDto
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


class PlayerAwardDto(BaseDto):
    """
    An award won by a player, or by several of them at once.

    `usernames` is a list because ties are frequent at this league size -- five
    picks each means scores land on the same handful of values -- and picking
    one of them arbitrarily would be a lie about the week.
    """

    usernames: List[str]
    value: float
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0


class PickAwardDto(BaseDto):
    """An award won by one player's single pick."""

    username: str
    game_id: int
    team: TeamDto
    opponent: TeamDto
    line: float
    confidence: int
    result: PickOutcome
    points: float
    pick_count: int
    game_pick_count: int
    pick_share: float


class SideAwardDto(BaseDto):
    """An award won by one side of one game, league-wide."""

    game_id: int
    team: TeamDto
    opponent: TeamDto
    line: float
    result: PickOutcome
    margin: float
    pick_count: int
    game_pick_count: int
    pick_share: float
    confidence_total: float


class GameAwardDto(BaseDto):
    """An award won by a whole game rather than a side of it."""

    game_id: int
    home_team: TeamDto
    away_team: TeamDto
    home_pick_count: int
    away_pick_count: int


class WeekAwardsDto(BaseDto):
    """
    The week's stories, not a second statistics table.

    Every award is optional and is left out when the week produced nothing
    worth saying -- nobody went perfect, no contrarian pick came in. Forcing a
    winner into every slot every week is how a section like this stops being
    read.
    """

    # Players
    player_of_the_week: PlayerAwardDto | None = None
    perfect_week: PlayerAwardDto | None = None
    ice_cold: PlayerAwardDto | None = None
    value_hunter: PlayerAwardDto | None = None
    dog_lover: PlayerAwardDto | None = None
    oracle: PickAwardDto | None = None

    # Games and the league
    most_confident: SideAwardDto | None = None
    consensus_miss: SideAwardDto | None = None
    sleeper: SideAwardDto | None = None
    biggest_cover: SideAwardDto | None = None
    photo_finish: SideAwardDto | None = None
    split_decision: GameAwardDto | None = None


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
    unanimous_picks: List[NotablePickDto] = Field(default_factory=list)
    confidence_breakdown: List[ConfidenceBreakdownDto] = Field(default_factory=list)
    games: List[GameBreakdownDto] = Field(default_factory=list)
    awards: WeekAwardsDto = Field(default_factory=WeekAwardsDto)
