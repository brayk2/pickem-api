from fastapi import APIRouter
from playhouse.shortcuts import model_to_dict

from src.config.logger import get_logger
from src.models.db_models import GameModel, SpreadModel, PropertyModel
from src.models.dto.admin_dtos import ApiQuota

admin_router = APIRouter(prefix="/admin", tags=["Admin"])

logger = get_logger(__name__)


@admin_router.post("/create-table")
def create_table():
    GameModel.create_table()
    SpreadModel.create_table()

    GameModel.select()
    SpreadModel.select()
    return {
        "msg": f"Successfully created table: {GameModel.__name__}, {SpreadModel.__name__}"
    }


@admin_router.get("/books", response_model=list[str])
def get_books():
    query = (
        SpreadModel.select(SpreadModel.bookmaker)
        .distinct()
        .order_by(SpreadModel.bookmaker)
    )

    logger.info(f"query: {query.sql()}")
    return [model.bookmaker for model in query]


@admin_router.get("/api-quota", response_model=ApiQuota)
def get_quota():
    model = PropertyModel.get(PropertyModel.key == "odds-api")
    return model_to_dict(model).get("value")
