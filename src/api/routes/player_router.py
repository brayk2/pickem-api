from fastapi import APIRouter
from src.config.logger import get_logger
from src.models.dto.player_dtos import Player, PlayerRequest
from src.services.player_service import PlayerService

logger = get_logger(__name__)
player_service = PlayerService()

player_router = APIRouter(prefix="/player", tags=["Player"])


@player_router.post("", response_model=Player)
def create_player(request: PlayerRequest):
    return player_service.create_player(request=request)


@player_router.delete("/{id}")
def delete_player(id: int):
    return player_service.delete_player(id=id)


@player_router.get("/list", response_model=list[Player])
def list_players():
    return player_service.list_players()
