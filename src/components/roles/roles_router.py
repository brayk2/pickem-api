from fastapi import APIRouter, Depends, status

from src.components.auth.permission_checker import PermissionChecker
from src.components.roles.roles_models import RoleCreateDto, RoleDto, AddUserToRoleDto
from src.components.roles.roles_service import RolesService
from src.components.user.user_service import UserService

roles_router = APIRouter(
    prefix="/roles", tags=["Roles"], dependencies=[Depends(PermissionChecker.admin)]
)


@roles_router.post("", status_code=status.HTTP_201_CREATED, response_model=RoleDto)
async def create_role(
    role_data: RoleCreateDto, role_service: RolesService = Depends(RolesService.create)
):
    role = role_service.create_role(
        name=role_data.name, description=role_data.description
    )
    return role


@roles_router.get("", response_model=list[RoleDto])
async def list_roles(role_service: RolesService = Depends(RolesService.create)):
    roles = role_service.get_all_roles()
    return roles


@roles_router.delete(
    "/{role_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(PermissionChecker.admin)],
)
async def delete_role(
    role_name: str, role_service: RolesService = Depends(RolesService.create)
):
    role_service.delete_role(role_name=role_name)


@roles_router.post("/add-user", status_code=status.HTTP_200_OK)
async def add_user_to_role(
    role_data: AddUserToRoleDto,
    user_service: UserService = Depends(UserService.create),
):
    user_service.add_user_to_role(username=role_data.username, role_name=role_data.role)
    return {"detail": "User added to role successfully"}
