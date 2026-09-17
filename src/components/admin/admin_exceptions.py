from fastapi import HTTPException, status


class PropertyNotFoundException(HTTPException):
    def __init__(self, key: str, category: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with key '{key}' in category '{category}' not found",
        )


class InvalidPropertyValueException(HTTPException):
    def __init__(self, key: str, value: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value '{value}' for property '{key}'",
        )


class WeekNotSetException(HTTPException):
    def __init__(self, detail: str = "Current season not set"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class SetCurrentWeekException(HTTPException):
    def __init__(self, detail: str = "Error setting current season"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )
