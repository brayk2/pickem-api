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
    # The scraper creates weeks without dates, so these are absent far more
    # often than not; requiring them made /admin/weeks fail on real rows.
    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None
    completed: bool = False
