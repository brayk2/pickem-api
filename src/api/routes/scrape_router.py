from fastapi import APIRouter
from pydantic import BaseModel
from src.config.logger import get_logger
from src.services.scrapers.nfl_scraper import NflScraper
from src.services.scrapers.pfr_scraper import PfrScraper

logger = get_logger(__name__)
pfr_scraper = PfrScraper()
nfl_scraper = NflScraper()

scrape_router = APIRouter(prefix="/scrape", tags=["Scraper"])


class GenericResponse(BaseModel):
    error: bool
    message: str


@scrape_router.post("/teams", response_model=GenericResponse)
def scape_teams():
    try:
        pfr_scraper.scrape_teams()
        return {
            "error": False,
            "message": f"Successfully scraped teams from {pfr_scraper.base_url}",
        }
    except Exception as e:
        return {"error": True, "message": f"Failed to scrape teams: {e}"}


@scrape_router.post("/schedule", response_model=GenericResponse)
def scape_schedule():
    try:
        pfr_scraper.scrape_schedule()
        return {
            "error": False,
            "message": f"Successfully scraped schedule from {pfr_scraper.base_url}",
        }
    except Exception as e:
        return {"error": True, "message": f"Failed to scrape schedule: {e}"}


@scrape_router.post("/thumbnails", response_model=GenericResponse)
def scape_thumbnails():
    try:
        nfl_scraper.scrape_thumbnails()
        return {
            "error": False,
            "message": f"Successfully scraped thumbnails from {nfl_scraper.base_url}",
        }
    except Exception as e:
        return {"error": True, "message": f"Failed to scrape thumbnails: {e}"}
