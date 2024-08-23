from pydantic import BaseModel


class SetCurrentWeekRequest(BaseModel):
    week: int


class SetCurrentWeekResponse(BaseModel):
    message: str
    week: int
