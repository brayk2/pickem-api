# This is the exceptions.py file for standings

from fastapi import HTTPException, status


class StandingsCalculationException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )
