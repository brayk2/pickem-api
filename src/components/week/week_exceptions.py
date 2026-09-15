from fastapi import HTTPException


class WeekNotFoundException(HTTPException):
    def __init__(self, year: int, week: int):
        super().__init__(
            status_code=404, detail=f"Week {week} of the {year} season does not exist"
        )
