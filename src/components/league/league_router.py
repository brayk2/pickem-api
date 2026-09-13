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

league_router = APIRouter(prefix="/league", tags=["Leagues"])


@league_router.get("", response_model=list[LeagueDto])
async def list_leagues(league_service: LeagueService = Depends(LeagueService.create)):
    return league_service.list_leagues()


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


@league_router.get("/{league_id}/seasons", response_model=list[LeagueSeasonDto])
async def list_league_seasons(
    league_id: int = Path(description="The league to list seasons for."),
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
