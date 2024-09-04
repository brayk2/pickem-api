from datetime import datetime

import pytz
from peewee import fn, Case, JOIN

from src.components.results.results_dto import MatchupDto, TeamDto
from src.config.base_service import BaseService
from src.models.new_db_models import (
    SpreadModel,
    GameModel,
    TeamModel,
    SeasonModel,
    TeamResultModel,
    WeekModel,
)
from src.services.odds_api_service import (
    OddsApiService,
    OddsDto,
)
from src.util.injection import dependency, inject


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

    def load_spreads(self, start_date: datetime, end_date: datetime):
        season_model = SeasonModel.get(year=2024)
        self.logger.info(f"using season {season_model}")

        response: list[OddsDto] = self.oddsapi_service.fetch_odds(
            start_date=start_date, end_date=end_date
        )
        self.logger.info(f"found {len(response)} odds marker")

        for item in response:
            # parse cities and team names
            home_city, home_team_name = item.home_team.rsplit(" ", 1)
            away_city, away_team_name = item.away_team.rsplit(" ", 1)
            self.logger.info(f"found matchup {home_city} vs {away_city}")

            # load team models
            home_team_model = TeamModel.get(city=home_city, name=home_team_name)
            away_team_model = TeamModel.get(city=away_city, name=away_team_name)
            self.logger.info(
                f"found matchup models {home_team_model} vs {away_team_model}"
            )

            # parse tz
            new_york = pytz.timezone("America/New_York")
            start_time = item.start_time.astimezone(new_york)

            # create the game model
            try:
                game = GameModel.get(
                    season=season_model,
                    home_team=home_team_model,
                    away_team=away_team_model,
                    start_date=start_time.replace(tzinfo=None).date(),
                )
            except Exception:
                self.logger.info(
                    f"failed to find game {season_model.year} {home_team_name} vs {away_team_name}"
                )
                continue

            game.oddsapi_id = item.game_id
            game.save()

            self.logger.info(f"found {len(item.bookmakers)} bookmakers")
            for spread in item.bookmakers:
                self.logger.info(f"spread = {spread}")

                for outcome in spread.markets[0].outcomes:
                    self.logger.info(f"outcome = {outcome}")

                    if outcome.name == game.home_team.full_name:
                        self.logger.info(
                            f"setting home lines for spread, game = {game.oddsapi_id}"
                        )

                        # home team spread
                        home_spread_model: SpreadModel
                        home_spread_model, _ = SpreadModel.get_or_create(
                            bookmaker=spread.title,
                            game=game,
                            team=game.home_team,
                            defaults={"spread_value": 0},
                        )
                        home_spread_model.spread_value = outcome.point
                        home_spread_model.save()

                        self.logger.info(
                            f"updated spread for {home_spread_model} {game} {spread}"
                        )
                    elif outcome.name == game.away_team.full_name:
                        self.logger.info(
                            f"setting away lines for spread, game = {game.oddsapi_id}"
                        )

                        # away team spread
                        away_spread_model: SpreadModel
                        away_spread_model, _ = SpreadModel.get_or_create(
                            bookmaker=spread.title,
                            game=game,
                            team=game.away_team,
                            defaults={"spread_value": 0},
                        )
                        away_spread_model.spread_value = outcome.point
                        away_spread_model.save()

                        self.logger.info(
                            f"updated spread for {away_spread_model} {game} {spread}"
                        )

    async def get_matchup_data(self, year: int, week: int, bookmaker: str):
        # define aliased
        home_team_alias = TeamModel.alias("home_team")
        away_team_alias = TeamModel.alias("away_team")
        home_result_alias = TeamResultModel.alias("home_result")
        away_result_alias = TeamResultModel.alias("away_result")

        # Query to get the necessary data, including the thumbnail
        games = (
            GameModel.select(
                GameModel.id.alias("game_id"),
                GameModel.start_date,
                GameModel.start_time,
                home_team_alias.id.alias("home_team_id"),
                home_team_alias.name.alias("home_team_name"),
                home_team_alias.city.alias("home_team_city"),
                home_team_alias.thumbnail.alias("home_team_thumbnail"),
                home_team_alias.primary_color.alias("home_team_primary"),
                home_team_alias.secondary_color.alias("home_team_secondary"),
                away_team_alias.id.alias("away_team_id"),
                away_team_alias.name.alias("away_team_name"),
                away_team_alias.city.alias("away_team_city"),
                away_team_alias.thumbnail.alias("away_team_thumbnail"),
                away_team_alias.primary_color.alias("away_team_primary"),
                away_team_alias.secondary_color.alias("away_team_secondary"),
                fn.COUNT(home_result_alias.team_id).alias("home_team_games_played"),
                fn.SUM(Case(None, [(home_result_alias.win, 1)], 0)).alias(
                    "home_team_wins"
                ),
                fn.COUNT(away_result_alias.team_id).alias("away_team_games_played"),
                fn.SUM(Case(None, [(away_result_alias.win, 1)], 0)).alias(
                    "away_team_wins"
                ),
                home_result_alias.points_scored.alias("home_team_points_scored"),
                home_result_alias.points_allowed.alias("home_team_points_allowed"),
                home_result_alias.home.alias("home_team_is_home"),
                away_result_alias.points_scored.alias("away_team_points_scored"),
                away_result_alias.points_allowed.alias("away_team_points_allowed"),
                away_result_alias.home.alias("away_team_is_home"),
                WeekModel.week_number,
                # Aggregate the spread values into one row
                fn.SUM(
                    Case(
                        None,
                        [
                            (
                                SpreadModel.team == home_team_alias.id,
                                SpreadModel.spread_value,
                            )
                        ],
                        0,
                    )
                ).alias("home_spread_value"),
                fn.SUM(
                    Case(
                        None,
                        [
                            (
                                SpreadModel.team == away_team_alias.id,
                                SpreadModel.spread_value,
                            )
                        ],
                        0,
                    )
                ).alias("away_spread_value"),
            )
            .join(home_team_alias, on=(GameModel.home_team == home_team_alias.id))
            .join(away_team_alias, on=(GameModel.away_team == away_team_alias.id))
            .join(WeekModel, on=(GameModel.week == WeekModel.id))
            .join(SeasonModel, on=(GameModel.season == SeasonModel.id))
            .join(
                home_result_alias,
                JOIN.LEFT_OUTER,
                on=(
                    (GameModel.id == home_result_alias.game_id)
                    & (home_result_alias.team == home_team_alias.id)
                ),
            )
            .join(
                away_result_alias,
                JOIN.LEFT_OUTER,
                on=(
                    (GameModel.id == away_result_alias.game_id)
                    & (away_result_alias.team == away_team_alias.id)
                ),
            )
            .join(SpreadModel, JOIN.LEFT_OUTER, on=(GameModel.id == SpreadModel.game))
            .where(
                WeekModel.week_number == week,
                SeasonModel.year == year,
                SpreadModel.bookmaker == bookmaker,
            )
            .group_by(
                GameModel.id,
                GameModel.start_date,
                GameModel.start_time,
                home_team_alias.id,
                home_team_alias.name,
                home_team_alias.city,
                home_team_alias.thumbnail,
                home_team_alias.primary_color,
                home_team_alias.secondary_color,
                away_team_alias.id,
                away_team_alias.name,
                away_team_alias.city,
                away_team_alias.thumbnail,
                away_team_alias.primary_color,
                away_team_alias.secondary_color,
                home_result_alias.points_scored,
                home_result_alias.points_allowed,
                home_result_alias.home,
                away_result_alias.points_scored,
                away_result_alias.points_allowed,
                away_result_alias.home,
                WeekModel.week_number,
            )
            .order_by(GameModel.start_date, GameModel.start_time)
        )

        # Return as dictionary list for further processing
        return self._convert_to_dtos(list(games.dicts()))

    @classmethod
    def calculate_losses(cls, team_results):
        # Assuming team_results is a list of all games played by the team
        total_games = len(team_results)
        wins = sum(1 for result in team_results if result.win)
        losses = total_games - wins
        return losses

    @classmethod
    def _convert_to_dtos(cls, games):
        try:
            return [
                MatchupDto(
                    game_id=game["game_id"],
                    home_team=TeamDto(
                        team_id=game["home_team_id"],
                        team_city=game["home_team_city"],
                        team_name=game["home_team_name"],
                        thumbnail=game["home_team_thumbnail"],
                        primary_color=game["home_team_primary"],
                        secondary_color=game["home_team_secondary"],
                    ),
                    away_team=TeamDto(
                        team_id=game["away_team_id"],
                        team_city=game["away_team_city"],
                        team_name=game["away_team_name"],
                        thumbnail=game["away_team_thumbnail"],
                        primary_color=game["away_team_primary"],
                        secondary_color=game["away_team_secondary"],
                    ),
                    results={
                        game["home_team_name"]: game["home_team_points_scored"],
                        game["away_team_name"]: game["away_team_points_scored"],
                    },
                    record={
                        game[
                            "home_team_name"
                        ]: f"{game['home_team_wins']}-{game['home_team_games_played'] - game['home_team_wins']}",
                        game[
                            "away_team_name"
                        ]: f"{game['away_team_wins']}-{game['away_team_games_played'] - game['away_team_wins']}",
                    },
                    ats={
                        game[
                            "home_team_name"
                        ]: f"{game.get('home_team_cover', 0)}-{game.get('home_team_not_cover', 0)}",
                        game[
                            "away_team_name"
                        ]: f"{game.get('away_team_cover', 0)}-{game.get('away_team_not_cover', 0)}",
                    },
                    home_record={
                        game[
                            "home_team_name"
                        ]: f"{game.get('home_team_home_wins', 0)}-{game.get('home_team_home_losses', 0)}"
                    },
                    away_record={
                        game[
                            "away_team_name"
                        ]: f"{game.get('away_team_home_wins', 0)}-{game.get('away_team_home_losses', 0)}"
                    },
                    lines={
                        game[
                            "home_team_name"
                        ]: f"{game['home_spread_value']:.1f}".rstrip("0").rstrip("."),
                        game[
                            "away_team_name"
                        ]: f"{game['away_spread_value']:.1f}".rstrip("0").rstrip("."),
                    },
                    start_date=game["start_date"],
                    start_time=game["start_time"],
                )
                for game in games
            ]
        except Exception as e:
            print(e)


if __name__ == "__main__":
    service = SpreadService()
    w = 1
    week: WeekModel = WeekModel.get(week_number=w)
    service.load_spreads(start_date=week.start_date, end_date=week.end_date)
