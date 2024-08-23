from fastapi import HTTPException, status


class InvalidWeekException(HTTPException):
    def __init__(self, week: int):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid week number: {week}",
        )


class InvalidYearException(HTTPException):
    def __init__(self, year: int):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid year: {year}",
        )


class WeekNotSetException(HTTPException):
    def __init__(self, detail: str = "Current week not set"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class YearNotSetException(HTTPException):
    def __init__(self, detail: str = "Current year not set"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class SetCurrentWeekException(HTTPException):
    def __init__(self, detail: str = "Error setting current week"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


class SetCurrentYearException(HTTPException):
    def __init__(self, detail: str = "Error setting current year"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )
