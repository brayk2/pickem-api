from fastapi import APIRouter, Depends, status

from src.components.auth.auth_models import DecodedToken
from src.components.auth.permission_checker import PermissionChecker
from src.components.user.user_models import (
    CreateUserDto,
    AddRoleDto,
    UserDto,
    UpdateUserPasswordRequest,
    UpdateUserRequest,
)
from src.components.user.user_service import UserService
from src.services.oauth_service import OAuthService

user_router = APIRouter(prefix="/users", tags=["Users"])


@user_router.post("", status_code=status.HTTP_201_CREATED, response_model=UserDto)
async def create_user(
    user_data: CreateUserDto,
    user_service: UserService = Depends(UserService.create),
    oauth_service: OAuthService = Depends(OAuthService.create),
    _: DecodedToken = Depends(PermissionChecker.commissioner),
):
    user = user_service.create_user(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        username=user_data.username,
        email=user_data.email,
        password_hash=oauth_service.get_password_hash(password=user_data.password),
    )
    return UserDto.model_validate(user)


@user_router.post("/add-role", status_code=status.HTTP_200_OK)
async def add_role_to_user(
    role_data: AddRoleDto,
    user_service: UserService = Depends(UserService.create),
    _: DecodedToken = Depends(PermissionChecker.admin),
):
    user_service.add_user_to_role(username=role_data.username, role_name=role_data.role)
    return {"detail": "Role added successfully"}


@user_router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    user_service: UserService = Depends(UserService.create),
    _: DecodedToken = Depends(PermissionChecker.admin),
):
    user_service.delete_user(username=username)


@user_router.put(
    "/password",
    status_code=status.HTTP_200_OK,
    response_model=UserDto,
    response_model_exclude={"is_admin", "is_commissioner"},
)
async def update_password(
    request: UpdateUserPasswordRequest,
    user_service: UserService = Depends(UserService.create),
    token: DecodedToken = Depends(PermissionChecker.player),
):
    return user_service.update_password(
        username=token.sub,
        update_password_request=request,
    )


@user_router.put(
    "/{username}",
    status_code=status.HTTP_200_OK,
    response_model=UserDto,
    response_model_exclude={"is_admin", "is_commissioner"},
)
async def update_user_profile(
    username: str,
    request: UpdateUserRequest,
    user_service: UserService = Depends(UserService.create),
    token: DecodedToken = Depends(PermissionChecker.player),
):
    return user_service.update_user_profile(
        username=username,
        update_user_request=request,
        token=token,
    )


@user_router.get("", status_code=status.HTTP_200_OK, response_model=UserDto)
async def get_user_from_token(
    user_service: UserService = Depends(UserService.create),
    token: DecodedToken = Depends(PermissionChecker.player),
):
    return user_service.get_user(username=token.sub)


@user_router.get("/{username}", status_code=status.HTTP_200_OK, response_model=UserDto)
async def get_user(
    username: str,
    user_service: UserService = Depends(UserService.create),
):
    return user_service.get_user(username=username)
