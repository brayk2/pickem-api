from fastapi import APIRouter, Depends
from .season_service import SeasonService
from src.components.auth.permission_checker import PermissionChecker
from src.components.season.season_dtos import (
    GetCurrentWeekAndYearResponseDto,
    SetCurrentWeekResponseDto,
    GetCurrentYearResponseDto,
    SetCurrentYearResponseDto,
)

season_router = APIRouter(prefix="/season", tags=["Season"])


@season_router.get("/current/week", response_model=GetCurrentWeekAndYearResponseDto)
async def get_current_week_and_year(
    season_service: SeasonService = Depends(SeasonService.create),
    _=Depends(PermissionChecker.player),
):
    """
    Gets the current week and year from the property table under the 'season' category.
    """
    return season_service.get_current_week_and_year()


@season_router.put("/current/week", response_model=SetCurrentWeekResponseDto)
async def set_current_week(
    week: int,
    season_service: SeasonService = Depends(SeasonService.create),
    _=Depends(PermissionChecker.admin),
):
    """
    Sets the current week in the property table under the 'season' category.
    """
    return season_service.set_current_week(week)


@season_router.get("/current/year", response_model=GetCurrentYearResponseDto)
async def get_current_year(
    season_service: SeasonService = Depends(SeasonService.create),
    _=Depends(PermissionChecker.player),
):
    """
    Gets the current year from the property table under the 'season' category.
    """
    return season_service.get_current_year()


@season_router.put("/current/year", response_model=SetCurrentYearResponseDto)
async def set_current_year(
    year: int,
    season_service: SeasonService = Depends(SeasonService.create),
    _=Depends(PermissionChecker.admin),
):
    """
    Sets the current year in the property table under the 'season' category.
    """
    return season_service.set_current_year(year)


@season_router.get("/info")
async def get_season_info(
    season_service: SeasonService = Depends(SeasonService.create),
    _=Depends(PermissionChecker.player),
):
    """
    Placeholder endpoint for season info retrieval.
    """
    season_service.get_season_info()
