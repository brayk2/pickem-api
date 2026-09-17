from src.components.season.season_service import SeasonService
from src.config.logger import Logger
from src.lambdas.utils import connect_db
from src.models.db_models import WeekModel, SeasonModel
from src.components.spread.spread_service import SpreadService

logger = Logger()


@connect_db
def handle_event(event, context):
    logger.info(f"initializing with event={event} and context={context}")

    spread_service = SpreadService()
    season_service = SeasonService()

    try:
        week = season_service.get_current_week_and_year()
        year = week.get("year")

        season = SeasonModel.get(year=year)
        week_model = WeekModel.get(week_number=week.get("week"), season=season)
        spread_service.load_spreads(
            year=year, start_date=week_model.start_date, end_date=week_model.end_date
        )
    except Exception as e:
        logger.exception(f"failed to load spreads: {e}")
        raise e


if __name__ == "__main__":
    handle_event({}, {})
