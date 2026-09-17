import logging
from fastapi import APIRouter, Depends, Query

from src.security.security_models import DecodedToken
from src.security.permission_checker import PermissionChecker
from src.components.league.league_permission import LeaguePermission
from src.components.results.results_models import (
    UserPickResultsDto,
    LeaguePickResultsDto,
    GameResultDto,
    MatchupDto,
    WeekResultsDto,
)
from src.components.results.results_service import ResultsService
from src.components.results.results_stats_models import WeekStatsDto
from src.components.results.results_stats_service import ResultsStatsService
from src.config.logger import Logger
from src.components.spread.spread_service import SpreadService

results_router = APIRouter(
    prefix="/results",
    tags=["Results"],
)


@results_router.get("/{league_id}/{year}/{week}/user-picks", response_model=UserPickResultsDto)
async def get_user_pick_results(
    league_id: int,
    year: int,
    week: int,
    results_service: ResultsService = Depends(ResultsService.create),
    logger: Logger = Depends(Logger),
    token: DecodedToken = Depends(LeaguePermission.league_member),
):
    logger.info(f"Getting user pick results for year {year} and week {week}")
    if picks := await results_service.get_user_pick_results(
        year, week, league_id=league_id, user=token.sub
    ):
        return picks[0]
    return UserPickResultsDto(username=token.sub, picks=[], total_score=0, rank=None)


@results_router.get("/{league_id}/{year}/user-picks", response_model=UserPickResultsDto)
async def get_season_user_pick_results(
    league_id: int,
    year: int,
    results_service: ResultsService = Depends(ResultsService.create),
    logger: Logger = Depends(Logger),
    token: DecodedToken = Depends(LeaguePermission.league_member),
):
    """
    Every graded pick you have made this season, in one answer.

    The per-week route above answers for one week, which meant the profile's
    team counts asked it eighteen times to fill a single card. Ungraded picks
    are absent rather than pending: only concluded games are returned, so this
    reaches as far into the season as results have, and no further.

    `rank` is deliberately null. The score here is a season total for one
    player, with nobody to rank them against -- returning the 1 that ranking a
    single-row result produces would read as a league position.
    """
    logger.info(f"Getting season pick results for league {league_id}, {year}")
    if results := await results_service.get_season_pick_results(
        year, league_id=league_id, user=token.sub
    ):
        season = results[0]
        season.rank = None
        return season
    return UserPickResultsDto(username=token.sub, picks=[], total_score=0, rank=None)


@results_router.get("/{league_id}/{year}/{week}/history", response_model=list[WeekResultsDto])
async def get_user_pick_history(
    league_id: int,
    year: int,
    week: int,
    _: DecodedToken = Depends(LeaguePermission.league_member),
    results_service: ResultsService = Depends(ResultsService.create),
    logger: Logger = Depends(Logger),
):
    logger.info(f"Getting user pick results for year {year} and week {week}")
    return await results_service.get_pick_history_for_year(
        year, week, league_id=league_id
    )


@results_router.get(
    "/{league_id}/{year}/{week}/league-picks",
    response_model=list[UserPickResultsDto],
)
async def get_league_pick_results(
    league_id: int,
    year: int,
    week: int,
    results_service: ResultsService = Depends(ResultsService.create),
    token: DecodedToken = Depends(LeaguePermission.league_member),
    logger: Logger = Depends(Logger),
):
    """
    The week's table, with a row for every player on the season's roster.

    A selection never appears here before its game has been graded -- the query
    behind `picks` joins on a final score, so an ungraded pick has no row to
    come from. What does appear, once the week has opened, is the confidence
    levels each player has staked: `submittedConfidences`, numbers only. Enough
    to see that somebody has their 5 and their 3 in, or that somebody has
    nothing in; never enough to see what they took.
    """
    logger.info(f"Getting league pick results for year {year} and week {week}")
    return await results_service.get_league_week_results(
        year, week, league_id=league_id
    )


@results_router.get("/{league_id}/{year}/{week}/stats", response_model=WeekStatsDto)
async def get_week_stats(
    league_id: int,
    year: int,
    week: int,
    stats_service: ResultsStatsService = Depends(ResultsStatsService.create),
    _: DecodedToken = Depends(LeaguePermission.league_member),
    logger: Logger = Depends(Logger),
):
    """
    End-of-week statistics for the league: how it split on each game, which
    picks it got right and wrong, and how each confidence level paid.

    Returns `completed: false` and nothing else until the week is finished, so
    the page can hold the panel back rather than showing numbers that will
    change once the last game is scored.
    """
    logger.info(f"Getting week stats for league {league_id}, {year} week {week}")
    return await stats_service.get_week_stats(year=year, week=week, league_id=league_id)


@results_router.get("/{year}/{week}/nfl-games", response_model=list[MatchupDto])
async def get_nfl_game_results(
    year: int,
    week: int,
    _: DecodedToken = Depends(PermissionChecker.authenticated),
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
