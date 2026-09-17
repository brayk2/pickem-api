from pydantic import BaseModel

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
