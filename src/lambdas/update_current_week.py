from src.components.season.season_service import SeasonService
from src.config.logger import Logger
from src.lambdas.utils import connect_db


logger = Logger()


@connect_db
def handle_event(event, context):
    service = SeasonService()
    lookup = service.get_current_week_and_year()
    try:
        return service.set_current_week(week=lookup.get("week", 0) + 1)
    except Exception as e:
        logger.exception(f"failed to load spreads: {e}")
        raise e


if __name__ == "__main__":
    handle_event({}, {})
