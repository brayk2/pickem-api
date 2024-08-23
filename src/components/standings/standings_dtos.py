from pydantic import BaseModel


class StandingsDto(BaseModel):
    username: str
    rank: int
    correct_picks: int  # Number of correct picks
    total_picks: int  # Total number of picks
    score: int  # Total score


class UserHistoryDto(BaseModel):
    username: str
    ranks: list[int]  # Rank per week, indexed by week number
    scores: list[int]  # Corresponding scores per week
    pcts: list[float]  # Corresponding pcsts per week


class StandingsHistoryDto(BaseModel):
    year: int
    weeks: list[int]  # List of week numbers
    users: list[UserHistoryDto]  # List of user ranking histories
