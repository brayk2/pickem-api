from pydantic import BaseModel


class GetCurrentWeekAndYearResponseDto(BaseModel):
    week: int
    year: int


class SetCurrentWeekResponseDto(BaseModel):
    week: int
    year: int


class GetCurrentYearResponseDto(BaseModel):
    year: int


class SetCurrentYearResponseDto(BaseModel):
    year: int
