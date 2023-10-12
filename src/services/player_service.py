from src.config.base_service import BaseService
from src.models.db_models import PlayerModel
from src.models.dto.player_dtos import PlayerRequest
from src.util.injection import inject, dependency


@dependency
class PlayerService(BaseService):
    @inject
    def __init__(self):
        pass

    def create_player(self, request: PlayerRequest):
        self.logger.info(f"creating player: {request.username}")
        return PlayerModel.create(username=request.username, email=request.email)

    def delete_player(self, id: int):
        self.logger.info(f"deleting player: {id}")
        return PlayerModel.delete_by_id(id)

    def list_players(
        self,
    ):
        self.logger.info(f"fetching all players")
        return PlayerModel.select().order_by(PlayerModel.username)
