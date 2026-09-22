from starlette.exceptions import HTTPException
from starlette import status


class InvalidGameIDException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidSeasonException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidTeamIDException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidWeekException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class LockedPickException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class TooManyPicksException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class InvalidGameWeekException(HTTPException):
    def __init__(self, game_id: int, expected_year: int, expected_week: int):
        super().__init__(
            status_code=400,
            detail=f"Game ID {game_id} does not belong to the expected year {expected_year} and week {expected_week}.",
        )


class InvalidSlateException(HTTPException):
    """
    An override that would leave the week in a shape the player's own
    submission could never have produced -- a repeated game, or confidence
    levels that are not exactly 1 through 5.

    The player path cannot reach this: its UI always submits an ordered slate,
    and nothing in the database stops two picks sharing a confidence. Scoring
    is a plain sum, so a duplicated 5 would quietly inflate a total with no
    error anywhere. This is the check that has to catch it.
    """

    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class LockOverrideNotAcknowledgedException(HTTPException):
    """
    An override that would change a game which has already kicked off, without
    `overrideLocked` set.

    Separate from LockedPickException, which means "you may not do this at
    all". This one means "you may, but say so first" -- so an admin fixing a
    Tuesday typo cannot silently rewrite Sunday on the same request.
    """

    def __init__(self, game_ids: list[int]):
        games = ", ".join(str(game_id) for game_id in sorted(game_ids))
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This change touches game(s) {games}, which have already started. "
                f"Resubmit with overrideLocked set to confirm."
            ),
        )


class PathBodyMismatchException(HTTPException):
    """
    An override whose body claims a different week from the one in the path.

    The path is what the caller navigated to and what the confirmation screen
    named, so a disagreeing body is a client bug, and believing it would write
    the right picks into the wrong week.
    """

    def __init__(self, path: str, body: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"This request is for {path}, but its body describes {body}."),
        )


class OverrideNotFoundException(HTTPException):
    """
    A revert naming an override that is not in this league-season.

    Scoped rather than a bare id lookup: an override id from another league
    would otherwise be revertible by anyone who commissions this one.
    """

    def __init__(self, override_id: int, league_id: int, year: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Override {override_id} was not found for league {league_id} "
                f"in {year}."
            ),
        )
