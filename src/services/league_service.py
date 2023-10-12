# league crud service

from src.config.base_service import BaseService
from src.models.db_models import LeagueModel, LeaguePlayerRelationModel, PlayerModel
from src.models.dto.league_dtos import League, LeagueRequest
from src.models.dto.player_dtos import Player
from src.util.injection import dependency, inject


@dependency
class LeagueService(BaseService):
    @inject
    def __init__(self):
        pass

    def get_league(self, id: int):
        query = LeaguePlayerRelationModel.select(PlayerModel).join(
            PlayerModel, attr="player"
        )
        self.logger.info(f"query: {query.sql()}")

        league = League.model_validate(LeagueModel.get_by_id(id))
        league.players = [Player.model_validate(rel.player) for rel in query]

        return league

    def create_league(self, request: LeagueRequest) -> League:
        raise NotImplementedError("get league is not implemented")

    def update_league(self, id: int, request: LeagueRequest) -> League:
        raise NotImplementedError("get league is not implemented")

    def delete_league(self, id: int):
        raise NotImplementedError("get league is not implemented")
