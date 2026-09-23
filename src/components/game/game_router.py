from fastapi import APIRouter, Depends

from src.security.permission_checker import PermissionChecker
from src.components.game.game_models import Game
from src.components.game.game_service import GameService

game_router = APIRouter(
    prefix="/game",
    tags=["Game"],
    dependencies=[Depends(PermissionChecker.authenticated)],
)


@game_router.get("/{year}/{week}", response_model=list[Game])
async def get_games(
    year: int, week: int, game_service: GameService = Depends(GameService.create)
):
    return game_service.get_games(year=year, week=week)


@game_router.get("/{id}", response_model=Game)
async def get_game(id: int, game_service: GameService = Depends(GameService.create)):
    return game_service.get_game(game_id=id)
