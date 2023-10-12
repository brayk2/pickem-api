import functools

import peewee

from src.config.logger import get_logger
from src.models.db_models import (
    GameModel,
    SpreadModel,
    ResultsModel,
)
from src.services.odds_api_service import OddsApiService
from src.services.spread_service import SpreadService

logger = get_logger(__name__)


def process_response(response: list[dict]):
    for item in response:
        game, created = GameModel.get_or_create(
            oddsapi_id=item.get("id"),
        )

        game.home_team = item.get("home_team")
        game.away_team = item.get("away_team")
        game.start_time = item.get("commence_time")

        game.save()

        if created:
            logger.info(f"found new game {game.id}")
        else:
            logger.info(f"game {game.id} already loaded.")

        home_point_spread, home_spread_price = None, None
        away_point_spread, away_spread_price = None, None

        for spread in item.get("bookmakers"):
            for outcome in spread.get("markets")[0].get("outcomes"):
                if outcome.get("name") == game.home_team:
                    logger.info(f"setting home lines for spread, game = {game.id}")
                    home_point_spread = outcome.get("point")
                    home_spread_price = outcome.get("price")
                elif outcome.get("name") == game.away_team:
                    logger.info(f"setting away lines for spread, game = {game.id}")
                    away_point_spread = outcome.get("point")
                    away_spread_price = outcome.get("price")

            try:
                spread_model = SpreadModel.create(
                    bookmaker=spread.get("title"),
                    game=game,
                    home_point_spread=home_point_spread,
                    home_spread_price=home_spread_price,
                    away_point_spread=away_point_spread,
                    away_spread_price=away_spread_price,
                )
                logger.info(
                    f"created spread model book = {spread_model.bookmaker}, game = {spread_model.game_id}"
                )
            except peewee.IntegrityError as e:
                logger.error(f"failed to create: {e}")


if __name__ == "__main__":
    # odds_api_key
    service = SpreadService()
    service.load_results()
