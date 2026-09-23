from fastapi import APIRouter, Depends, Path
from starlette import status

from src.security.security_models import DecodedToken
from src.security.permission_checker import PermissionChecker
from src.components.league.league_permission import LeaguePermission
from src.components.pick.pick_models import (
    AdminSubmitPicksRequestDto,
    PickOverrideDto,
    RevertOverrideRequestDto,
    SubmitPicksRequestDto,
    SubmitPicksResponseDto,
    UserPicksDto,
)
from src.components.pick.pick_service import PickService

picks_router = APIRouter(
    prefix="/pick",
    tags=["Picks"],
    dependencies=[Depends(PermissionChecker.authenticated)],
)


# Route order is load-bearing below. Starlette matches in declaration
# order, and `/{league_id}/{year}/{week_number}` happily matches a literal
# fourth segment -- so `/1/2026/overrides` resolves to it and then 422s
# trying to read "overrides" as a week. Every route whose fourth segment is
# a literal is declared before it.


@picks_router.put(
    "/{league_id}",
    response_model=SubmitPicksResponseDto,
    status_code=status.HTTP_201_CREATED,
)
async def submit_picks(
    pick_data: SubmitPicksRequestDto,
    league_id: int = Path(description="The league these picks are for."),
    decoded_token: DecodedToken = Depends(PermissionChecker.authenticated),
    pick_service: PickService = Depends(PickService.create),
):
    return await pick_service.submit_picks(
        pick_data, league_id=league_id, token=decoded_token
    )


@picks_router.get(
    "/{league_id}/{year}/overrides",
    response_model=list[PickOverrideDto],
    status_code=status.HTTP_200_OK,
)
async def list_overrides(
    league_id: int,
    year: int,
    _: DecodedToken = Depends(LeaguePermission.commissioner),
    pick_service: PickService = Depends(PickService.create),
):
    """
    The league-season's override log, newest first.

    Commissioner-gated like the write that produces it: the log names players
    and the picks they had, so it is not less sensitive than the editor.
    """
    return pick_service.list_overrides(league_id=league_id, year=year)


@picks_router.post(
    "/{league_id}/{year}/overrides/{override_id}/revert",
    response_model=SubmitPicksResponseDto,
    status_code=status.HTTP_200_OK,
)
async def revert_override(
    league_id: int,
    year: int,
    override_id: int,
    request: RevertOverrideRequestDto | None = None,
    token: DecodedToken = Depends(LeaguePermission.commissioner),
    pick_service: PickService = Depends(PickService.create),
):
    """
    Put a week back the way the named override found it.

    POST rather than DELETE, because nothing is deleted. The entry stays in the
    log and a second one is appended saying it was undone -- a log that can be
    edited cannot answer the question it exists for, and the entry most likely
    to be removed is the one somebody most wants gone.
    """
    return await pick_service.revert_override(
        override_id=override_id,
        league_id=league_id,
        year=year,
        token=token,
        reason=request.reason if request else None,
    )


@picks_router.get(
    "/{league_id}/{year}/player/{username}/overrides",
    response_model=list[PickOverrideDto],
    status_code=status.HTTP_200_OK,
)
async def get_player_override_history(
    league_id: int,
    year: int,
    username: str = Path(description="The player whose override history to read."),
    _: DecodedToken = Depends(LeaguePermission.commissioner),
    pick_service: PickService = Depends(PickService.create),
):
    """Every override recorded against this player's season, newest first."""
    return pick_service.get_override_history(
        league_id=league_id, year=year, username=username
    )


@picks_router.get(
    "/{league_id}/{year}/{week_number}",
    response_model=UserPicksDto,
    status_code=status.HTTP_200_OK,
)
async def get_user_picks_for_week(
    league_id: int,
    year: int,
    week_number: int,
    decoded_token: DecodedToken = Depends(LeaguePermission.league_member),
    pick_service: PickService = Depends(PickService.create),
):
    return pick_service.get_own_picks_for_week(
        username=decoded_token.sub,
        year=year,
        week_number=week_number,
        league_id=league_id,
    )


@picks_router.get(
    "/{league_id}/{year}/{week_number}/player/{username}",
    response_model=UserPicksDto,
    status_code=status.HTTP_200_OK,
)
async def get_player_picks_for_week(
    league_id: int,
    year: int,
    week_number: int,
    username: str = Path(description="The player whose picks to read."),
    _: DecodedToken = Depends(LeaguePermission.commissioner),
    pick_service: PickService = Depends(PickService.create),
):
    """
    Another player's picks for a week, for an admin or commissioner about to
    change them.

    This is the one route in the application that shows an ungraded pick to
    somebody other than the player who made it, and it is deliberately its own
    route rather than a parameter on the player's. Results deliberately reveal
    only confidence levels before a game is graded (see
    ResultsService.get_submitted_confidences); nothing about that changes, and
    no non-commissioner reaches this path.
    """
    return pick_service.get_player_picks_for_week(
        username=username, year=year, week_number=week_number, league_id=league_id
    )


@picks_router.put(
    "/{league_id}/{year}/{week_number}/player/{username}",
    response_model=SubmitPicksResponseDto,
    status_code=status.HTTP_200_OK,
)
async def override_player_picks(
    pick_data: AdminSubmitPicksRequestDto,
    league_id: int,
    year: int,
    week_number: int,
    username: str = Path(description="The player whose picks to replace."),
    token: DecodedToken = Depends(LeaguePermission.commissioner),
    pick_service: PickService = Depends(PickService.create),
):
    """
    Replace a player's whole week, kickoff locks included.

    Not a PATCH, and not `?as=` on the player's own route. A separate verb on a
    separate path is what keeps "who did this" unambiguous in the audit row --
    an impersonation header would have made every route in the application
    silently act-as-able, and would have recorded the wrong name besides.

    The year and week in the path are authoritative; a body that disagrees is
    rejected rather than quietly believed, since the path is what the caller
    navigated to and saw.
    """
    return await pick_service.override_picks(
        pick_data,
        username=username,
        league_id=league_id,
        year=year,
        week_number=week_number,
        token=token,
    )
