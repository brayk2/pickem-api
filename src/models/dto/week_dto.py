import datetime

from pydantic import BaseModel, ConfigDict


class SeasonDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int


class WeekDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: SeasonDto
    week_number: int
    start_date: datetime.datetime
    end_date: datetime.datetime
