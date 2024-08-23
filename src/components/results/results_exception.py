from fastapi import HTTPException


class ResultsNotFoundException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=404, detail="Results not found for the specified week and year"
        )
