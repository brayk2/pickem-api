from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.services.scrapers.espn_scraper import EspnScraper
from src.services.scrapers.nfl_scraper import NflScraper
from src.services.scrapers.pfr_scraper import PfrScraper

pfr_scraper = PfrScraper()
espn_scraper = EspnScraper()
nfl_scraper = NflScraper()

scrape_router = APIRouter(prefix="/scrape", tags=["Scraper"])


class GenericResponse(BaseModel):
    error: bool
    message: str


@scrape_router.post("/teams", response_model=GenericResponse)
async def scape_teams():
    try:
        pfr_scraper.scrape_teams()
        return {
            "error": False,
            "message": f"Successfully scraped teams from {pfr_scraper.base_url}",
        }
    except Exception as e:
        return {"error": True, "message": f"Failed to scrape teams: {e}"}


@scrape_router.post("/schedule", response_model=GenericResponse)
async def scape_schedule(year: int = Query(default=2024)):
    try:
        espn_scraper.scrape_season(year=year)
        return {
            "error": False,
            "message": f"Successfully scraped schedule from {espn_scraper.base_url}",
        }
    except Exception as e:
        return {"error": True, "message": f"Failed to scrape schedule: {e}"}


@scrape_router.post("/thumbnails", response_model=GenericResponse)
async def scape_thumbnails():
    try:
        nfl_scraper.scrape_thumbnails()
        return {
            "error": False,
            "message": f"Successfully scraped thumbnails from {nfl_scraper.base_url}",
        }
    except Exception as e:
        return {"error": True, "message": f"Failed to scrape thumbnails: {e}"}
