from src.models.base_models import BaseDto


class WeekCompletionDto(BaseDto):
    """The completion state of a single week, as returned by the admin override."""

    year: int
    week: int
    completed: bool


class SetWeekCompletionRequest(BaseDto):
    completed: bool
