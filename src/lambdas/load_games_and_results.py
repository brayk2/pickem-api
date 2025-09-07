from src.components.season.season_service import SeasonService
from src.config.logger import Logger
from src.lambdas.utils import connect_db
from src.services.scrapers.espn_scraper import EspnScraper

logger = Logger()


@connect_db
def handle_event(event, context):
    logger.info(
        f"Initializing lambda to load games and results with event={event} and context={context}"
    )

    scraper = EspnScraper()
    season_service = SeasonService()

    try:
        year = season_service.get_current_year()
        logger.info(f"loading games and results for year {year}")
        scraper.scrape_season(year=year.get("year"))
        logger.info(f"successfully scraped {year} season data")
    except Exception as e:
        logger.exception(f"failed to load season: {e}")
        raise e


if __name__ == "__main__":
    handle_event({}, {})
