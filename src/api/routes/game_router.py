from fastapi import APIRouter
from src.config.logger import get_logger
from src.models.db_models import GameModel, SeasonModel
from src.models.dto.dto import Game

logger = get_logger(__name__)
game_router = APIRouter(prefix="/game", tags=["Game"])


@game_router.get("/{year}/{week}", response_model=list[Game])
def get_games(year: int, week: int):
    games = (
        GameModel.select()
        .join(SeasonModel)
        .where((GameModel.season.year == f"{year}") & (GameModel.week == f"{week}"))
    )

    return games


@game_router.get("/{id}", response_model=Game)
def get_game(id: int):
    return GameModel.get_by_id(id)
