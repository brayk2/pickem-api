from starlette import status
from starlette.exceptions import HTTPException


class LeagueNotFoundException(HTTPException):
    def __init__(self, league_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"League {league_id} does not exist.",
        )


class LeagueSeasonNotFoundException(HTTPException):
    def __init__(self, league_id: int, year: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"League {league_id} did not run in {year}.",
        )


class NotALeagueMemberException(HTTPException):
    def __init__(self, username: str, league_id: int, year: int):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User {username} is not a member of league {league_id} for {year}.",
        )


class DuplicateLeagueMemberException(HTTPException):
    def __init__(self, username: str, year: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User {username} is already a member for {year}.",
        )


class DuplicateLeagueException(HTTPException):
    def __init__(self, name: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A league named '{name}' already exists.",
        )


class NotALeagueCommissionerException(HTTPException):
    def __init__(self, username: str, league_id: int):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User {username} is not a commissioner of league {league_id}.",
        )
