from fastapi import APIRouter
from src.config.logger import get_logger
from src.models.dto.dto import Spread
from src.services.spread_service import SpreadService

logger = get_logger(__name__)
spread_service = SpreadService()

spread_router = APIRouter(prefix="/spreads", tags=["Spreads"])


@spread_router.get("/{id}/{bookmaker}", response_model=Spread)
def get_spread(id: int, bookmaker: str):
    return spread_service.get_spread(game_id=id, bookmaker=bookmaker)
