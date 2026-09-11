from fastapi import APIRouter, Depends, Query
from playhouse.shortcuts import model_to_dict

from src.components.admin.admin_exception import (
    PropertyNotFoundException,
)
from src.components.admin.admin_service import AdminService, PaginationOptions
from src.components.auth.auth_models import DecodedToken
from src.components.auth.permission_checker import PermissionChecker
from src.config.logger import Logger
from src.models.dto.action_dto import CreateActionRequest
from src.models.dto.admin_dtos import ApiQuota
from src.models.dto.group_dto import CreateGroupRequest, CreateGroupResponse
from src.models.new_db_models import GameModel, SpreadModel, GroupModel

admin_router = APIRouter(
    prefix="/admin", tags=["Admin"], dependencies=[Depends(PermissionChecker.admin)]
)


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


@admin_router.get("/weeks")
async def get_week_information(
    season: int, admin_service: AdminService = Depends(AdminService.create)
):
    return admin_service.get_week_information(season=season)


@admin_router.get("/actions")
async def get_actions(admin_service: AdminService = Depends(AdminService.create)):
    return admin_service.get_actions()


@admin_router.get("/executions/{state_machine_arn}")
async def get_executions(
    state_machine_arn: str, admin_service: AdminService = Depends(AdminService.create)
):
    return admin_service.get_executions(state_machine_arn=state_machine_arn)


@admin_router.get("/executions/{state_machine_arn}/{execution_arn}")
async def get_execution(
    state_machine_arn: str,
    execution_arn: str,
    max_results: int = Query(default=10),
    next_token: str = Query(default=None),
    admin_service: AdminService = Depends(AdminService.create),
):
    return admin_service.get_execution(
        state_machine_arn=state_machine_arn,
        execution_arn=execution_arn,
        pagination_options=PaginationOptions(
            max_results=max_results, next_token=next_token
        ),
    )


@admin_router.get("/schedulers")
async def get_schedulers(admin_service: AdminService = Depends(AdminService.create)):
    return admin_service.get_schedulers()


@admin_router.post("/action/{state_machine_arn}")
async def trigger_state_machine(
    state_machine_arn: str, admin_service: AdminService = Depends(AdminService.create)
):
    return admin_service.trigger_action(state_machine_arn=state_machine_arn)
