from fastapi import APIRouter, Depends, Path
from starlette import status

from src.security.security_models import DecodedToken
from src.security.permission_checker import PermissionChecker
from src.components.league.league_permission import LeaguePermission
from src.components.pick.pick_models import (
    SubmitPicksRequestDto,
    SubmitPicksResponseDto,
    UserPicksDto,
)
from src.models.db_models import UserModel
from src.components.pick.pick_service import PickService

picks_router = APIRouter(
    prefix="/pick", tags=["Picks"], dependencies=[Depends(PermissionChecker.authenticated)]
)


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
    user = UserModel.get(username=decoded_token.sub)
    pick_status = await pick_service.submit_picks(
        pick_data, user, league_id=league_id, token=decoded_token
    )
    return {"detail": "Picks submitted successfully.", "status": pick_status}


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
    user = UserModel.get(username=decoded_token.sub)
    user_picks = pick_service.get_user_picks_for_week(
        user, year, week_number, league_id=league_id
    )
    return user_picks
