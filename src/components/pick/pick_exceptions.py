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
