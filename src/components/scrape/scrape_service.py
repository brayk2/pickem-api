from src.components.scrape.scrape_models import GenericResponse
from src.components.scrape.scrapers.espn_scraper import EspnScraper
from src.components.scrape.scrapers.nfl_scraper import NflScraper
from src.components.scrape.scrapers.pfr_scraper import PfrScraper
from src.config.base_service import BaseService
from src.util.injection import dependency, inject


@dependency
class ScrapeService(BaseService):
    """
    Runs the scrapers on demand.

    A failed scrape is reported in the response body rather than raised, so the
    admin console can show what went wrong.
    """

    @inject
    def __init__(
        self,
        pfr_scraper: PfrScraper,
        espn_scraper: EspnScraper,
        nfl_scraper: NflScraper,
    ):
        self.pfr_scraper = pfr_scraper
        self.espn_scraper = espn_scraper
        self.nfl_scraper = nfl_scraper

    def scrape_teams(self) -> GenericResponse:
        try:
            self.pfr_scraper.scrape_teams()
            return GenericResponse(
                error=False,
                message=f"Successfully scraped teams from {self.pfr_scraper.base_url}",
            )
        except Exception as e:
            return GenericResponse(error=True, message=f"Failed to scrape teams: {e}")

    def scrape_schedule(self, year: int) -> GenericResponse:
        try:
            self.espn_scraper.scrape_season(year=year)
            return GenericResponse(
                error=False,
                message=f"Successfully scraped schedule from {self.espn_scraper.base_url}",
            )
        except Exception as e:
            return GenericResponse(
                error=True, message=f"Failed to scrape schedule: {e}"
            )

    def scrape_thumbnails(self) -> GenericResponse:
        try:
            self.nfl_scraper.scrape_thumbnails()
            return GenericResponse(
                error=False,
                message=f"Successfully scraped thumbnails from {self.nfl_scraper.base_url}",
            )
        except Exception as e:
            return GenericResponse(
                error=True, message=f"Failed to scrape thumbnails: {e}"
            )
