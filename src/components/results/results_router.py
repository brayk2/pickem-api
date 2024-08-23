import logging
from fastapi import APIRouter, Depends, Query

from src.components.auth.auth_models import DecodedToken
from src.components.auth.permission_checker import PermissionChecker
from src.components.results.results_dto import (
    UserPickResultsDto,
    LeaguePickResultsDto,
    GameResultDto,
    MatchupDto,
    WeekResultsDto,
)
from src.components.results.results_service import ResultsService
from src.config.logger import Logger
from src.services.spread_service import SpreadService

results_router = APIRouter(
    prefix="/results",
    tags=["Results"],
)


@results_router.get("/{year}/{week}/user-picks", response_model=UserPickResultsDto)
async def get_user_pick_results(
    year: int,
    week: int,
    results_service: ResultsService = Depends(ResultsService.create),
    logger: Logger = Depends(Logger),
    token: DecodedToken = Depends(PermissionChecker.player),
):
    logger.info(f"Getting user pick results for year {year} and week {week}")
    if picks := await results_service.get_user_pick_results(year, week, token.sub):
        return picks[0]
    return UserPickResultsDto(username=token.sub, picks=[], total_score=0, rank=None)


@results_router.get("/{year}/{week}/history", response_model=list[WeekResultsDto])
async def get_user_pick_history(
    year: int,
    week: int,
    results_service: ResultsService = Depends(ResultsService.create),
    logger: Logger = Depends(Logger),
):
    logger.info(f"Getting user pick results for year {year} and week {week}")
    return await results_service.get_pick_history_for_year(year, week)


@results_router.get(
    "/{year}/{week}/league-picks", response_model=list[UserPickResultsDto]
)
async def get_league_pick_results(
    year: int,
    week: int,
    results_service: ResultsService = Depends(ResultsService.create),
    token: DecodedToken = Depends(PermissionChecker.player),
    logger: Logger = Depends(Logger),
):
    logger.info(f"Getting league pick results for year {year} and week {week}")
    user_results = await results_service.get_user_pick_results(year, week)
    return await results_service.get_league_results(user_results)


@results_router.get("/{year}/{week}/nfl-games", response_model=list[MatchupDto])
async def get_nfl_game_results(
    year: int,
    week: int,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(
        default=10, ge=1, le=100, description="Number of results per page"
    ),
    spread_service: SpreadService = Depends(SpreadService.create),
    logger: Logger = Depends(Logger),
):
    logger.info(
        f"Getting NFL game results for year {year} and week {week}, page {page}, page_size {page_size}"
    )
    x = await spread_service.get_matchup_data(
        year=year, week=week, bookmaker="DraftKings"
    )
    return x
