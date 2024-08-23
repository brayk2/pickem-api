from fastapi import APIRouter, Depends

from src.components.auth.permission_checker import PermissionChecker
from src.models.dto.dto import Game
from src.models.new_db_models import GameModel, SeasonModel

game_router = APIRouter(
    prefix="/game", tags=["Game"], dependencies=[Depends(PermissionChecker.player)]
)


@game_router.get("/{year}/{week}", response_model=list[Game])
async def get_games(year: int, week: int):
    games = (
        GameModel.select()
        .join(SeasonModel)
        .where((GameModel.season.year == f"{year}") & (GameModel.week == f"{week}"))
    )

    return games


@game_router.get("/{id}", response_model=Game)
async def get_game(id: int):
    return GameModel.get_by_id(id)
