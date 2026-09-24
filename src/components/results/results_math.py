"""
Small pure helpers for turning graded pick rows into statistics.

Shared by the week statistics and the season team statistics so both read a
game the same way -- the same modal line, the same margin, the same idea of a
rate with nothing to divide by.
"""

from collections import Counter
from statistics import mean

from src.components.results.results_models import TeamDto


def team_dto(row: dict, prefix: str) -> TeamDto:
    return TeamDto(
        team_id=row[f"{prefix}_id"],
        team_name=row[f"{prefix}_name"],
        team_city=row[f"{prefix}_city"],
        abbreviation=row[f"{prefix}_abbreviation"],
        thumbnail=row[f"{prefix}_thumbnail"],
        primary_color=row[f"{prefix}_primary_color"],
        secondary_color=row[f"{prefix}_secondary_color"],
    )


def rate(numerator: int, denominator: int) -> float | None:
    """None rather than 0.0 when there is nothing to divide by -- a week with no
    decided picks has an unknown hit rate, not a 0% one."""
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def average(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def modal_line(rows: list[dict]) -> float | None:
    """
    The line the side was most commonly taken at.

    Picks store the number the player took, so a line that moved mid-week leaves
    a game with two of them. The common value is what the week was played at.
    """
    if not rows:
        return None
    return Counter(float(row["spread_value"]) for row in rows).most_common(1)[0][0]


def margin(team_score: int, line: float, opponent_score: int) -> float:
    """Points this side beat its line by; negative means it fell short."""
    return round(team_score + line - opponent_score, 2)


def outcome(margin: float) -> str:
    if margin > 0:
        return "COVERED"
    if margin < 0:
        return "FAILED"
    return "PUSHED"
