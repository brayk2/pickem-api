from fastapi import APIRouter, Depends, Query

from src.components.admin.admin_service import AdminService, PaginationOptions
from src.security.security_models import DecodedToken
from src.security.permission_checker import PermissionChecker
from src.components.admin.admin_models import ApiQuota
from src.components.admin.admin_models import CreateGroupRequest, CreateGroupResponse
from src.components.week.week_models import (
    SetWeekCompletionRequest,
    WeekCompletionDto,
)
from src.components.week.week_service import WeekService

admin_router = APIRouter(
    prefix="/admin", tags=["Admin"], dependencies=[Depends(PermissionChecker.admin)]
)


@admin_router.post("/group", response_model=CreateGroupResponse)
async def create_group(
    request: CreateGroupRequest,
    admin_service: AdminService = Depends(AdminService.create),
    _: DecodedToken = Depends(PermissionChecker.admin),
):
    return admin_service.create_group(
        name=request.name, description=request.description
    )


@admin_router.get("/api-quota", response_model=ApiQuota)
async def get_quota(
    admin_service: AdminService = Depends(AdminService.create),
    _: DecodedToken = Depends(PermissionChecker.admin),
):
    """Gets the odds API quota."""
    return admin_service.get_api_quota()


@admin_router.get("/weeks")
async def get_week_information(
    season: int, admin_service: AdminService = Depends(AdminService.create)
):
    return admin_service.get_week_information(season=season)


@admin_router.put("/weeks/{year}/{week}/completion", response_model=WeekCompletionDto)
async def set_week_completion(
    year: int,
    week: int,
    request: SetWeekCompletionRequest,
    token: DecodedToken = Depends(PermissionChecker.admin),
    week_service: WeekService = Depends(WeekService.create),
):
    """
    Force a week open or closed.

    The scraper completes a week on its own once every game has a final score,
    so this is for the exceptions: holding a week back while a bad score is
    corrected, or releasing one whose last game will never be played. A week
    set here is left alone by the scraper from then on.
    """
    completed = week_service.set_completion(
        year=year, week=week, completed=request.completed, actor=token.sub
    )
    return WeekCompletionDto(year=year, week=week, completed=completed)


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
