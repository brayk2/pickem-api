from fastapi import APIRouter, Depends
from starlette import status

from src.components.auth.auth_models import DecodedToken
from src.components.auth.permission_checker import PermissionChecker
from src.components.pick.pick_models import (
    SubmitPicksRequestDto,
    SubmitPicksResponseDto,
    UserPicksDto,
)
from src.models.new_db_models import UserModel
from src.components.pick.pick_service import PickService

picks_router = APIRouter(
    prefix="/pick", tags=["Picks"], dependencies=[Depends(PermissionChecker.player)]
)


@picks_router.put(
    "", response_model=SubmitPicksResponseDto, status_code=status.HTTP_201_CREATED
)
async def submit_picks(
    pick_data: SubmitPicksRequestDto,
    decoded_token: DecodedToken = Depends(PermissionChecker.player),
    pick_service: PickService = Depends(PickService.create),
):
    user = UserModel.get(username=decoded_token.sub)
    pick_status = await pick_service.submit_picks(pick_data, user)
    return {"detail": "Picks submitted successfully.", "status": pick_status}


@picks_router.get(
    "/{year}/{week_number}",
    response_model=UserPicksDto,
    status_code=status.HTTP_200_OK,
)
async def get_user_picks_for_week(
    year: int,
    week_number: int,
    decoded_token: DecodedToken = Depends(PermissionChecker.player),
    pick_service: PickService = Depends(PickService.create),
):
    user = UserModel.get(username=decoded_token.sub)
    user_picks = pick_service.get_user_picks_for_week(user, year, week_number)
    return user_picks
