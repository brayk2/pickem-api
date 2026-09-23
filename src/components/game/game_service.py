from src.config.base_service import BaseService
from src.models.db_models import GameModel, SeasonModel
from src.util.injection import dependency


@dependency
class GameService(BaseService):
    def get_games(self, year: int, week: int):
        return (
            GameModel.select()
            .join(SeasonModel)
            .where((GameModel.season.year == f"{year}") & (GameModel.week == f"{week}"))
        )

    def get_game(self, game_id: int) -> GameModel:
        return GameModel.get_by_id(game_id)
