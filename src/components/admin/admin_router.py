from fastapi import APIRouter, Depends
from playhouse.shortcuts import model_to_dict

from src.components.admin.admin_exception import (
    PropertyNotFoundException,
)
from src.components.admin.admin_service import AdminService
from src.components.auth.permission_checker import PermissionChecker
from src.config.logger import Logger
from src.models.dto.admin_dtos import ApiQuota
from src.models.dto.group_dto import CreateGroupRequest, CreateGroupResponse
from src.models.new_db_models import GameModel, SpreadModel, GroupModel

admin_router = APIRouter(
    prefix="/admin", tags=["Admin"], dependencies=[Depends(PermissionChecker.admin)]
)


@admin_router.post("/create-table")
async def create_table():
    GameModel.create_table()
    SpreadModel.create_table()

    GameModel.select()
    SpreadModel.select()
    return {
        "msg": f"Successfully created table: {GameModel.__name__}, {SpreadModel.__name__}"
    }


@admin_router.get("/books", response_model=list[str])
async def get_books(logger: Logger = Depends(Logger)):
    query = (
        SpreadModel.select(SpreadModel.bookmaker)
        .distinct()
        .order_by(SpreadModel.bookmaker)
    )

    logger.info(f"query: {query.sql()}")
    return [model.bookmaker for model in query]


@admin_router.post("/group", response_model=CreateGroupResponse)
async def create_group(request: CreateGroupRequest):
    model = GroupModel.create(name=request.name, description=request.description)
    return model_to_dict(model)


@admin_router.get("/api-quota", response_model=ApiQuota)
async def get_quota(
    admin_service: AdminService = Depends(AdminService.create),
    # logger: Logger = Depends(Logger),
):
    """Gets the odds API quota."""
    try:
        model = admin_service.get_oddsapi_quota()
        return model_to_dict(model).get("value")
    except Exception as e:
        # logger.error(f"Error fetching API quota: {e}")
        raise PropertyNotFoundException("Error fetching API quota", category="api")
