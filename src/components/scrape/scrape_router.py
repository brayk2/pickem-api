from fastapi import APIRouter, Depends, Query

from src.security.permission_checker import PermissionChecker
from src.components.scrape.scrape_models import GenericResponse
from src.components.scrape.scrape_service import ScrapeService

# These write to the database (teams, schedules, thumbnails), so they are
# admin-only rather than open to anyone who knows the path.
scrape_router = APIRouter(
    prefix="/scrape",
    tags=["Scraper"],
    dependencies=[Depends(PermissionChecker.admin)],
)


@scrape_router.post("/teams", response_model=GenericResponse)
async def scape_teams(scrape_service: ScrapeService = Depends(ScrapeService.create)):
    return scrape_service.scrape_teams()


@scrape_router.post("/schedule", response_model=GenericResponse)
async def scape_schedule(
    year: int = Query(default=2024),
    scrape_service: ScrapeService = Depends(ScrapeService.create),
):
    return scrape_service.scrape_schedule(year=year)


@scrape_router.post("/thumbnails", response_model=GenericResponse)
async def scape_thumbnails(
    scrape_service: ScrapeService = Depends(ScrapeService.create),
):
    return scrape_service.scrape_thumbnails()
