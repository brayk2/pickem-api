from fastapi import APIRouter, Depends
from starlette import status

from src.components.auth.permission_checker import PermissionChecker
from src.components.user.user_models import UserDto
from src.components.user.user_service import UserService

users_router = APIRouter(
    prefix="/users", tags=["Users"], dependencies=[Depends(PermissionChecker.player)]
)


@users_router.get("", status_code=status.HTTP_200_OK, response_model=list[UserDto])
async def list_users(user_service: UserService = Depends(UserService.create)):
    return user_service.list_users()
