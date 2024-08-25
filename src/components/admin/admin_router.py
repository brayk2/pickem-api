from fastapi import APIRouter, Depends
from playhouse.shortcuts import model_to_dict

from src.components.admin.admin_exception import (
    PropertyNotFoundException,
)
from src.components.admin.admin_service import AdminService
from src.components.auth.auth_models import DecodedToken
from src.components.auth.permission_checker import PermissionChecker
from src.config.logger import Logger
from src.models.dto.admin_dtos import ApiQuota
from src.models.dto.group_dto import CreateGroupRequest, CreateGroupResponse
from src.models.new_db_models import GameModel, SpreadModel, GroupModel

admin_router = APIRouter(prefix="/admin", tags=["Admin"])


@admin_router.post("/group", response_model=CreateGroupResponse)
async def create_group(
    request: CreateGroupRequest, _: DecodedToken = Depends(PermissionChecker.admin)
):
    model = GroupModel.create(name=request.name, description=request.description)
    return model_to_dict(model)


@admin_router.get("/api-quota", response_model=ApiQuota)
async def get_quota(
    admin_service: AdminService = Depends(AdminService.create),
    _: DecodedToken = Depends(PermissionChecker.commissioner),
    # logger: Logger = Depends(Logger),
):
    """Gets the odds API quota."""
    try:
        model = admin_service.get_oddsapi_quota()
        return model_to_dict(model).get("value")
    except Exception as e:
        # logger.error(f"Error fetching API quota: {e}")
        raise PropertyNotFoundException("Error fetching API quota", category="api")
