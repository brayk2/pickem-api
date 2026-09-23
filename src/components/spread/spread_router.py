from fastapi import APIRouter, Depends

from src.security.permission_checker import PermissionChecker
from src.components.results.results_models import MatchupDto
from src.components.spread.spread_service import SpreadService

spread_router = APIRouter(
    prefix="/spreads",
    tags=["Spreads"],
    dependencies=[Depends(PermissionChecker.authenticated)],
)


@spread_router.get("/{year}/{week}/{bookmaker}", response_model=list[MatchupDto])
async def get_spreads_for_week(
    year: int,
    week: int,
    bookmaker: str,
    spread_service: SpreadService = Depends(SpreadService.create),
):
    return await spread_service.get_matchup_data(
        year=year, week=week, bookmaker=bookmaker
    )
