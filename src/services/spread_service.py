import datetime

import peewee
from pydantic import BaseModel, Field

from src.config.base_service import BaseService
from src.models.db_models import SpreadModel, GameModel, ResultsModel
from src.services.odds_api_service import (
    OddsApiService,
    OddsDto,
    OutcomeDto,
    ScoresDto,
)
from src.util.injection import dependency, inject

"""
response model = {
    commence_time
    completed
    home_team
    away_team
    scores
}
"""


@dependency
class SpreadService(BaseService):
    @inject
    def __init__(self, oddsapi_service: OddsApiService):
        self.oddsapi_service = oddsapi_service

    def get_spread(self, game_id: int, bookmaker: str) -> SpreadModel:
        self.logger.info(f"fetching spread for game {game_id} and book {bookmaker}")
        return SpreadModel.get(
            (SpreadModel.game_id == game_id) & (SpreadModel.bookmaker == bookmaker)
        )

    def load_spreads(self):
        response: list[OddsDto] = self.oddsapi_service.fetch_odds()
        for item in response:
            game, created = GameModel.get_or_create(
                home_team=item.home_team,
                away_team=item.away_team,
                start_time=item.start_time,
            )
            game.oddsapi_id = item.game_id
            game.save()

            if created:
                self.logger.info(f"found new game {game.oddsapi_id}")
            else:
                self.logger.info(f"game {game.oddsapi_id} already loaded.")

            home_point_spread, home_spread_price = None, None
            away_point_spread, away_spread_price = None, None

            for spread in item.bookmakers:
                for outcome in spread.markets[0].outcomes:
                    if outcome.name == game.home_team:
                        self.logger.info(
                            f"setting home lines for spread, game = {game.oddsapi_id}"
                        )
                        home_point_spread = outcome.point
                        home_spread_price = outcome.price
                    elif outcome.name == game.away_team:
                        self.logger.info(
                            f"setting away lines for spread, game = {game.oddsapi_id}"
                        )
                        away_point_spread = outcome.point
                        away_spread_price = outcome.price

                try:
                    spread_model = SpreadModel.create(
                        bookmaker=spread.title,
                        game=game,
                        home_point_spread=home_point_spread,
                        home_spread_price=home_spread_price,
                        away_point_spread=away_point_spread,
                        away_spread_price=away_spread_price,
                    )
                    self.logger.info(
                        f"created spread model book = {spread_model.bookmaker}, game = {spread_model.game_id}"
                    )
                except peewee.IntegrityError as e:
                    self.logger.error(f"failed to create: {e}")

    def load_results(self):
        response: list[ScoresDto] = self.oddsapi_service.fetch_scores()
        for item in response:
            if scores := item.scores:
                home_score, away_score = 0, 0
                for score in scores:
                    if score.name == item.home_team:
                        home_score = score.score
                    elif score.name == item.away_team:
                        away_score = score.score

                try:
                    game = GameModel.get(GameModel.oddsapi_id == item.game_id)
                    self.logger.info(f"loaded game {game.oddsapi_id}")
                except peewee.DoesNotExist:
                    self.logger.info(f"failed to load {item.game_id}")
                    continue

                try:
                    result, created = ResultsModel.get_or_create(
                        game=game,
                    )
                    result.home_score = home_score
                    result.away_score = away_score
                    result.completed = item.completed

                    result.save()
                    self.logger.info(f"created result for {game.oddsapi_id} - {result}")
                except peewee.IntegrityError as e:
                    self.logger.error(f"failed to create: {e}")
            else:
                self.logger.info("no scores available")
