from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.models.db_models import GameModel

# Kickoff is stored as a naive date plus a `time without time zone`, scraped
# from ESPN's server-rendered schedule, which renders in US Eastern. The zone is
# not stored anywhere, so it has to be applied when the value is read.
#
# The webapp does the same thing in src/utils/timeUtils.js. Both must agree, or
# the button a player sees disagrees with what the API will accept.
LEAGUE_TIME_ZONE = ZoneInfo("America/New_York")


def kickoff(game: GameModel) -> datetime | None:
    """The absolute instant a game starts, or None when it is still TBD."""
    if not game.start_date or not game.start_time:
        return None

    return datetime.combine(game.start_date, game.start_time, tzinfo=LEAGUE_TIME_ZONE)


def has_started(game: GameModel, now: datetime | None = None) -> bool:
    """
    Whether kickoff has passed.

    A game with no scheduled time has not started: the schedule shows "TBD"
    until the league sets it, and an unknown kickoff must never lock a pick.
    """
    starts_at = kickoff(game)
    if starts_at is None:
        return False

    return (now or datetime.now(tz=timezone.utc)) >= starts_at
