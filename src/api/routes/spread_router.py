from fastapi import APIRouter, Depends

from src.components.auth.permission_checker import PermissionChecker
from src.components.results.results_dto import MatchupDto
from src.services.spread_service import SpreadService

spread_service = SpreadService()
spread_router = APIRouter(
    prefix="/spreads",
    tags=["Spreads"],
    dependencies=[Depends(PermissionChecker.player)],
)


@spread_router.get("/{year}/{week}/{bookmaker}", response_model=list[MatchupDto])
async def get_spreads_for_week(
    year: int,
    week: int,
    bookmaker: str,
):
    x = await spread_service.get_matchup_data(year=year, week=week, bookmaker=bookmaker)
    return x
