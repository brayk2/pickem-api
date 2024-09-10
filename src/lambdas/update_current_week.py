from datetime import datetime, timezone

from src.components.season.season_service import SeasonService
from src.config.base_service import BaseService
from src.config.logger import Logger
from src.lambdas.utils import connect_db
from src.models.new_db_models import WeekModel
from src.util.injection import dependency, inject


class NoCurrentWeekException(Exception):
    pass


@dependency
class WeekUpdater(BaseService):
    @inject
    def __init__(self, logger: Logger, season_service: SeasonService):
        self.logger = logger
        self.season_service = season_service

    def get_expected_current_week(self):
        # Get the current UTC time
        now = datetime.now(tz=timezone.utc)
        self.logger.info(f"calculating current week : {now}")

        # Query the WeekModel to find the week where the current date falls between start_date and end_date
        current_week = (
            WeekModel.select()
            .where((WeekModel.start_date <= now) & (WeekModel.end_date >= now))
            .order_by(WeekModel.start_date)
            .first()
        )
        self.logger.info(f"found current week as {current_week}")

        # If no current week is found, check if we're beyond the last known end_date
        if not current_week:
            last_week = WeekModel.select().order_by(WeekModel.end_date.desc()).first()
            if last_week and now > last_week.end_date:
                self.logger.error("current date is out of range for the season")
                raise NoCurrentWeekException(
                    "The current date is beyond the last available week in the schedule."
                )
            else:
                raise NoCurrentWeekException("No current week found.")
        return current_week


@connect_db
def handle_event(event, context):
    week_service = WeekUpdater()
    season_service = SeasonService()

    week: WeekModel = week_service.get_expected_current_week()
    season_service.set_current_week(week=week.week_number)
    return {"message": f"set current week to {week.week_number}"}
