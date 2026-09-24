from typing import List

from pydantic import BaseModel, Field

from src.components.results.results_models import TeamDto
from src.components.results.results_stats_models import PickOutcome
from src.models.base_models import BaseDto


class StandingsDto(BaseModel):
    username: str
    rank: int
    correct_picks: float  # Number of correct picks
    total_picks: int  # Total number of picks
    score: float  # Total score


class UserHistoryDto(BaseModel):
    username: str
    ranks: list[int]  # Rank per week, indexed by week number
    scores: list[int]  # Corresponding scores per week
    pcts: list[float]  # Corresponding pcsts per week


class StandingsHistoryDto(BaseModel):
    year: int
    weeks: list[int]  # List of week numbers
    users: list[UserHistoryDto]  # List of user ranking histories


class LeagueSeasonStandingsDto(BaseDto):
    """
    One season's line in a league's history.

    `standings` carries the full table rather than just the winner, because the
    roster shows where each member placed and counting the rows is what says
    who played that year. `leader` is the same object as the top row, repeated
    for the callers that only want the name.
    """

    year: int
    in_progress: bool
    player_count: int
    leader: StandingsDto | None = None
    standings: list[StandingsDto] = []


# --- season team statistics -------------------------------------------------
#
# Everything below counts the league's picks, not the NFL season: a team's
# "record" here is how the league did when it picked that team.


class TeamWeekDto(BaseDto):
    """One week of a team's form: its own result against the spread."""

    week: int
    # None when the team's game had no picks at all, or it was a bye -- there
    # is no line on record to grade it against.
    result: PickOutcome | None = None
    pick_count: int = 0


class TeamBackerDto(BaseDto):
    """One player's history with one team."""

    username: str
    pick_count: int
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0
    points_won: float = 0.0


class TeamSeasonDto(BaseDto):
    """How the league has done with one team, season to date."""

    team: TeamDto
    pick_count: int = 0
    player_count: int = 0
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0
    hit_rate: float | None = None
    points_won: float = 0.0
    points_riding: int = 0
    points_missed: int = 0
    average_confidence: float | None = None
    # Picks on this team's opponents -- the league fading them -- graded from
    # the picker's side.
    against_count: int = 0
    against_covered_count: int = 0
    against_failed_count: int = 0
    against_pushed_count: int = 0
    form: List[TeamWeekDto] = Field(default_factory=list)
    backers: List[TeamBackerDto] = Field(default_factory=list)


class TeamAwardDto(BaseDto):
    """A team singled out for the season so far."""

    team: TeamDto
    value: float
    pick_count: int = 0
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0


class TeamSeasonAwardsDto(BaseDto):
    """Each is left out when the season hasn't produced one yet."""

    money_team: TeamAwardDto | None = None
    money_pit: TeamAwardDto | None = None
    sure_thing: TeamAwardDto | None = None
    least_trusted: TeamAwardDto | None = None
    most_picked: TeamAwardDto | None = None
    underrated: TeamAwardDto | None = None


class TeamSeasonStatsDto(BaseDto):
    year: int
    through_week: int
    pick_count: int = 0
    covered_count: int = 0
    failed_count: int = 0
    pushed_count: int = 0
    hit_rate: float | None = None
    points_won: float = 0.0
    points_riding: int = 0
    teams: List[TeamSeasonDto] = Field(default_factory=list)
    # Teams that played in a picked game but were never picked themselves.
    # Teams whose games nobody touched don't appear anywhere in the picks, so
    # this is not necessarily every unpicked team in the league.
    never_picked: List[TeamDto] = Field(default_factory=list)
    awards: TeamSeasonAwardsDto = Field(default_factory=TeamSeasonAwardsDto)
