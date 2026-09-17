from fastapi import APIRouter, Depends, Path
from starlette import status

from src.components.auth.auth_models import DecodedToken
from src.components.auth.permission_checker import PermissionChecker
from src.components.league.league_permission import LeaguePermission
from src.components.league.league_models import (
    AddLeagueMemberRequest,
    CreateLeagueRequest,
    LeagueDto,
    LeagueMemberDto,
    LeagueRosterDto,
    LeagueSeasonDto,
)
from src.components.league.league_service import LeagueService
from src.components.standings.standings_dtos import LeagueSeasonStandingsDto
from src.components.standings.standings_service import StandingsService

league_router = APIRouter(prefix="/league", tags=["Leagues"])


@league_router.get("", response_model=list[LeagueDto])
async def list_leagues(
    token: DecodedToken = Depends(PermissionChecker.authenticated),
    league_service: LeagueService = Depends(LeagueService.create),
):
    """Only the caller's own leagues. Admins see every league."""
    return league_service.list_leagues(token=token)


@league_router.post(
    "", response_model=LeagueDto, status_code=status.HTTP_201_CREATED
)
async def create_league(
    request: CreateLeagueRequest,
    _: DecodedToken = Depends(PermissionChecker.admin),
    league_service: LeagueService = Depends(LeagueService.create),
):
    return league_service.create_league(
        name=request.name, description=request.description
    )


@league_router.get(
    "/{league_id}/history", response_model=list[LeagueSeasonStandingsDto]
)
async def get_league_history(
    league_id: int,
    standings_service: StandingsService = Depends(StandingsService.create),
    _: DecodedToken = Depends(LeaguePermission.league_member),
):
    """
    Every season this league has played, newest first, each with its table.

    One answer for the whole history. The alternative -- and what the web app
    did -- is a standings request per season, which costs a query, a full
    grading pass and an invocation for every year the league has existed, and
    grows by one more every autumn.

    A season is in progress until every week in it is marked complete, so the
    last line has a leader where the rest have champions.
    """
    return standings_service.get_league_history(league_id=league_id)


@league_router.get("/{league_id}/seasons", response_model=list[LeagueSeasonDto])
async def list_league_seasons(
    league_id: int = Path(description="The league to list seasons for."),
    _: DecodedToken = Depends(LeaguePermission.league_member),
    league_service: LeagueService = Depends(LeagueService.create),
):
    return league_service.list_league_seasons(league_id=league_id)


@league_router.post(
    "/{league_id}/seasons/{year}",
    response_model=LeagueSeasonDto,
    status_code=status.HTTP_201_CREATED,
)
async def start_season(
    league_id: int,
    year: int,
    _: DecodedToken = Depends(LeaguePermission.commissioner),
    league_service: LeagueService = Depends(LeagueService.create),
):
    """Opens a league for a new year. The roster starts empty."""
    return league_service.start_season(league_id=league_id, year=year)


@league_router.get("/{league_id}/seasons/{year}/members", response_model=LeagueRosterDto)
async def get_roster(
    league_id: int,
    year: int,
    _: DecodedToken = Depends(LeaguePermission.league_member),
    league_service: LeagueService = Depends(LeagueService.create),
):
    return league_service.get_roster(league_id=league_id, year=year)


@league_router.post(
    "/{league_id}/seasons/{year}/members",
    response_model=LeagueMemberDto,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    request: AddLeagueMemberRequest,
    league_id: int,
    year: int,
    _: DecodedToken = Depends(LeaguePermission.commissioner),
    league_service: LeagueService = Depends(LeagueService.create),
):
    return league_service.add_member(
        league_id=league_id,
        year=year,
        username=request.username,
        role=request.role,
    )


@league_router.delete(
    "/{league_id}/seasons/{year}/members/{username}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    league_id: int,
    year: int,
    username: str,
    _: DecodedToken = Depends(LeaguePermission.commissioner),
    league_service: LeagueService = Depends(LeagueService.create),
):
    league_service.remove_member(league_id=league_id, year=year, username=username)
