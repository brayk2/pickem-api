import asyncio

from src.components.results.results_dto import (
    UserPickResultsDto,
    WeekResultsDto,
    GameResultDto,
    TeamDto,
    GameDto,
    PickDto,
    LeaguePickResultsDto,
    MatchupDto,  # New DTO to encapsulate results by week
)
from src.config.base_service import BaseService
from src.models.new_db_models import (
    PickModel,
    UserModel,
    GameResultModel,
    TeamModel,
    GameModel,
    SeasonModel,
    WeekModel,
)
from src.util.injection import dependency, inject

_user = UserModel.alias()
_team = TeamModel.alias()
_away_team = TeamModel.alias()
_home_team = TeamModel.alias()
_game = GameModel.alias()
_pick = PickModel.alias()
_game_result = GameResultModel.alias()
_season = SeasonModel.alias()
_week_model = WeekModel.alias()


@dependency
class ResultsService(BaseService):
    @inject
    def __init__(self):
        super().__init__()

    async def _get_pick_results(
        self, year: int, week_condition, user: str = None
    ) -> list[UserPickResultsDto]:
        """
        get list of all picks filtered by user and week

        :param year:
        :param week_condition:
        :param user:
        :return:
        """
        query = (
            _pick.select(
                _pick.id,
                _user.username,
                _pick.game.alias("game_id"),
                _pick.spread_value,
                _pick.confidence,
                _pick.status,
                _team.id.alias("selected_team_id"),
                _team.name.alias("selected_team_name"),
                _team.city.alias("selected_team_city"),
                _team.thumbnail.alias("selected_team_thumbnail"),
                _team.primary_color.alias("selected_team_primary_color"),
                _team.secondary_color.alias("selected_team_secondary_color"),
                _home_team.id.alias("home_team_id"),
                _home_team.name.alias("home_team_name"),
                _home_team.city.alias("home_team_city"),
                _home_team.thumbnail.alias("home_team_thumbnail"),
                _home_team.primary_color.alias("home_team_primary_color"),
                _home_team.secondary_color.alias("home_team_secondary_color"),
                _away_team.id.alias("away_team_id"),
                _away_team.name.alias("away_team_name"),
                _away_team.city.alias("away_team_city"),
                _away_team.thumbnail.alias("away_team_thumbnail"),
                _away_team.primary_color.alias("away_team_primary_color"),
                _away_team.secondary_color.alias("away_team_secondary_color"),
                _game_result.home_score.alias("home_team_score"),
                _game_result.away_score.alias("away_team_score"),
            )
            .join(_user, on=(_pick.user == _user.id))
            .join(_game, on=(_pick.game == _game.id))
            .join(_team, on=(_pick.team == _team.id))
            .join(_home_team, on=(_game.home_team == _home_team.id))
            .join(_away_team, on=(_game.away_team == _away_team.id))
            .join(_game_result, on=(_game_result.game == _game.id))
            .join(_season, on=(_game.season == _season.id))
            .join(_week_model, on=(_game.week == _week_model.id))
            .where(
                _season.year == year,
                week_condition,
                _game_result.home_score.is_null(False),  # Ensure the game has concluded
                _game_result.away_score.is_null(False),  # Ensure the game has concluded
            )
        )

        if user:
            query = query.where(_user.username == user)

        self.logger.info(f"Query generated: {query.sql()}")
        picks = query.dicts()
        self.logger.info(f"Number of picks returned: {len(list(picks))}")

        user_results = {}
        for pick in picks:
            self.logger.debug(f"Processing pick: {pick}")
            pick_status = ""

            try:
                if (
                    pick["selected_team_id"] == pick["home_team_id"]
                    and (pick["home_team_score"] + pick["spread_value"])
                    > pick["away_team_score"]
                ) or (
                    pick["selected_team_id"] == pick["away_team_id"]
                    and (pick["away_team_score"] + pick["spread_value"])
                    > pick["home_team_score"]
                ):
                    pick_status = "COVERED"
                elif (
                    pick["selected_team_id"] == pick["home_team_id"]
                    and (pick["home_team_score"] + pick["spread_value"])
                    < pick["away_team_score"]
                ) or (
                    pick["selected_team_id"] == pick["away_team_id"]
                    and (pick["away_team_score"] + pick["spread_value"])
                    < pick["home_team_score"]
                ):
                    pick_status = "FAILED"
                elif (
                    pick["selected_team_id"] == pick["home_team_id"]
                    and (pick["home_team_score"] + pick["spread_value"])
                    == pick["away_team_score"]
                ) or (
                    pick["selected_team_id"] == pick["away_team_id"]
                    and (pick["away_team_score"] + pick["spread_value"])
                    == pick["home_team_score"]
                ):
                    pick_status = "PUSHED"
            except Exception as e:
                self.logger.exception(e)
                raise e

            multiplier = (
                1 if pick_status == "COVERED" else 0.5 if pick_status == "PUSHED" else 0
            )
            score = pick.get("confidence", 0) * multiplier

            if pick["username"] not in user_results:
                user_results[pick["username"]] = {
                    "username": pick["username"],
                    "picks": [],
                    "total_score": 0,
                    "rank": 0,  # To be calculated later
                }

            user_results[pick["username"]]["picks"].append(
                PickDto(
                    id=pick["id"],
                    team=TeamDto(
                        team_id=pick["selected_team_id"],
                        team_name=pick["selected_team_name"],
                        team_city=pick["selected_team_city"],
                        thumbnail=pick["selected_team_thumbnail"],
                        primary_color=pick["selected_team_primary_color"],
                        secondary_color=pick["selected_team_secondary_color"],
                    ),
                    confidence=pick["confidence"],
                    spread_value=pick["spread_value"],
                    status=pick["status"],
                    score=score,
                    pick_status=pick_status,
                )
            )
            user_results[pick["username"]]["total_score"] += score

        self.logger.info(f"Processed results for users: {list(user_results.keys())}")
        sorted_results = sorted(
            user_results.values(), key=lambda x: x["total_score"], reverse=True
        )
        for rank, result in enumerate(sorted_results, start=1):
            result["rank"] = rank

        return [UserPickResultsDto(**result) for result in sorted_results]

    async def get_user_pick_results(
        self, year: int, week: int, user: str = None
    ) -> list[UserPickResultsDto]:
        week_condition = _week_model.week_number == week
        return await self._get_pick_results(year, week_condition, user)

    import asyncio

    async def get_pick_history_for_year(
        self, year: int, week: int, user: str = None
    ) -> list[UserPickResultsDto]:
        return await self._get_pick_results(
            year=year, week_condition=_week_model.week_number <= week, user=user
        )

    async def _get_week_results_task(self, year: int, week: int, user: str):
        week_condition = _week_model.week_number == week
        results = await self._get_pick_results(year, week_condition, user)
        return WeekResultsDto(week=week, results=results)

    async def get_league_results(
        self, user_results: list[UserPickResultsDto]
    ) -> list[UserPickResultsDto]:
        return user_results

    async def get_nfl_game_results(
        self, year: int, week: int, page: int, page_size: int
    ) -> list[MatchupDto]:
        query = (
            _game_result.select(
                _game.id.alias("game_id"),
                _game.start_time.alias("start_time"),
                _home_team.id.alias("home_team_id"),
                _home_team.name.alias("home_team_name"),
                _home_team.city.alias("home_team_city"),
                _home_team.thumbnail.alias("home_team_thumbnail"),
                _away_team.id.alias("away_team_id"),
                _away_team.name.alias("away_team_name"),
                _away_team.city.alias("away_team_city"),
                _away_team.thumbnail.alias("away_team_thumbnail"),
                _game_result.home_score.alias("home_team_score"),
                _game_result.away_score.alias("away_team_score"),
                _pick.spread_value.alias("spread_value"),
                # Assuming records, ats, and other data are available in the appropriate tables
                # Additional fields for records, ATS, etc. would be joined or selected here
            )
            .join(_game, on=(_game_result.game == _game.id))
            .join(_home_team, on=(_game.home_team == _home_team.id))
            .join(_away_team, on=(_game.away_team == _away_team.id))
            .join(_season, on=(_game.season == _season.id))
            .join(_week_model, on=(_game.week == _week_model.id))
            .join(_pick, on=(_pick.game == _game.id))
            .where(_season.year == year, _week_model.week_number == week)
            .paginate(page, page_size)
        )

        game_results = query.dicts()

        results = []
        for game in game_results:
            lines = {
                game["home_team_name"]: f"{game['spread_value']:.1f}",
                game["away_team_name"]: f"{-game['spread_value']:.1f}",
            }

            # Placeholder values for ATS, record, and other fields
            ats = {
                game["home_team_name"]: "ATS Home Value",
                game["away_team_name"]: "ATS Away Value",
            }
            record = {
                game["home_team_name"]: "W-L",
                game["away_team_name"]: "W-L",
            }
            results_dict = {
                game["home_team_name"]: str(game["home_team_score"]),
                game["away_team_name"]: str(game["away_team_score"]),
            }
            home_record = {"home": "Home W-L"}
            away_record = {"away": "Away W-L"}

            matchup_data = MatchupDto(
                game_id=game["game_id"],
                start_time=game["start_time"],
                away_team=TeamDto(
                    team_id=game["away_team_id"],
                    team_name=game["away_team_name"],
                    team_city=game["away_team_city"],
                    thumbnail=game["away_team_thumbnail"],
                ),
                home_team=TeamDto(
                    team_id=game["home_team_id"],
                    team_name=game["home_team_name"],
                    team_city=game["home_team_city"],
                    thumbnail=game["home_team_thumbnail"],
                ),
                lines=lines,
                ats=ats,
                record=record,
                results=results_dict,
                home_record=home_record,
                away_record=away_record,
            )

            results.append(matchup_data)

        return results
