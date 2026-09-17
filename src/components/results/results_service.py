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
from src.models.db_models import (
    PickModel,
    UserModel,
    GameResultModel,
    TeamModel,
    GameModel,
    SeasonModel,
    WeekModel,
)
from src.components.league.league_service import LeagueService
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

# A covered pick is worth its confidence, a push half, a miss nothing.
PICK_MULTIPLIERS = {"COVERED": 1.0, "PUSHED": 0.5, "FAILED": 0.0}


def pick_margin(pick: dict) -> float | None:
    """
    Points by which the pick beat its line; negative means it fell short.

    Each pick stores the line the player took it at, so this is the selected
    team's final score plus that line, against its opponent's. A pick whose team
    is in neither slot of the game is a data fault rather than a result, and has
    no margin at all.
    """
    if pick["selected_team_id"] == pick["home_team_id"]:
        adjusted = pick["home_team_score"] + pick["spread_value"]
        opponent_score = pick["away_team_score"]
    elif pick["selected_team_id"] == pick["away_team_id"]:
        adjusted = pick["away_team_score"] + pick["spread_value"]
        opponent_score = pick["home_team_score"]
    else:
        return None

    return float(adjusted - opponent_score)


def grade_pick(pick: dict) -> str:
    """
    Whether a pick beat its line -- the sign of its margin. An ungradeable pick
    scores nothing rather than silently counting as a miss.
    """
    margin = pick_margin(pick)
    if margin is None:
        return "UNKNOWN"
    if margin > 0:
        return "COVERED"
    if margin < 0:
        return "FAILED"
    return "PUSHED"


def score_pick(pick_status: str, confidence: int) -> float:
    return (confidence or 0) * PICK_MULTIPLIERS.get(pick_status, 0.0)


@dependency
class ResultsService(BaseService):
    @inject
    def __init__(self, league_service: LeagueService):
        super().__init__()
        self.league_service = league_service

    def _graded_picks_query(self, conditions: list):
        """
        The pick-and-result join that every graded-pick reader runs.

        Kept in one place because the columns are the contract: the leaderboard
        groups these rows by player, the week statistics group the same rows by
        game, and the league history groups them by season. What varies between
        those is the filter, so only the filter is a parameter.
        """
        return (
            _pick.select(
                _pick.id,
                _user.username,
                _pick.game.alias("game_id"),
                _pick.spread_value,
                _pick.confidence,
                _pick.status,
                _week_model.week_number,
                _team.id.alias("selected_team_id"),
                _team.name.alias("selected_team_name"),
                _team.city.alias("selected_team_city"),
                _team.abbreviation.alias("selected_team_abbreviation"),
                _team.thumbnail.alias("selected_team_thumbnail"),
                _team.primary_color.alias("selected_team_primary_color"),
                _team.secondary_color.alias("selected_team_secondary_color"),
                _home_team.id.alias("home_team_id"),
                _home_team.name.alias("home_team_name"),
                _home_team.city.alias("home_team_city"),
                _home_team.abbreviation.alias("home_team_abbreviation"),
                _home_team.thumbnail.alias("home_team_thumbnail"),
                _home_team.primary_color.alias("home_team_primary_color"),
                _home_team.secondary_color.alias("home_team_secondary_color"),
                _away_team.id.alias("away_team_id"),
                _away_team.name.alias("away_team_name"),
                _away_team.city.alias("away_team_city"),
                _away_team.abbreviation.alias("away_team_abbreviation"),
                _away_team.thumbnail.alias("away_team_thumbnail"),
                _away_team.primary_color.alias("away_team_primary_color"),
                _away_team.secondary_color.alias("away_team_secondary_color"),
                _game_result.home_score.alias("home_team_score"),
                _game_result.away_score.alias("away_team_score"),
                # Constant within a season, and the grouping key when a caller
                # asks for several at once.
                _season.year.alias("year"),
            )
            .join(_user, on=(_pick.user == _user.id))
            .join(_game, on=(_pick.game == _game.id))
            .join(_team, on=(_pick.team == _team.id))
            .join(_home_team, on=(_game.home_team == _home_team.id))
            .join(_away_team, on=(_game.away_team == _away_team.id))
            .join(_game_result, on=(_game_result.game == _game.id))
            .join(_season, on=(_game.season == _season.id))
            .join(_week_model, on=(_game.week == _week_model.id))
            .where(*conditions)
            # Ordered so a season's picks arrive as a season reads. Nothing
            # downstream depended on the previous order -- the results page
            # looks picks up by confidence -- but a flat list of ninety picks
            # in whatever order the planner chose is not something to hand out.
            .order_by(_season.year, _week_model.week_number, _pick.confidence.desc())
        )

    def _grade(self, query) -> list[dict]:
        """Run a graded-picks query and attach margin, status and score."""
        self.logger.info(f"Query generated: {query.sql()}")
        picks = list(query.dicts())
        self.logger.info(f"Number of picks returned: {len(picks)}")

        for pick in picks:
            pick["margin"] = pick_margin(pick)
            pick["pick_status"] = grade_pick(pick)
            pick["score"] = score_pick(pick["pick_status"], pick.get("confidence", 0))

        return picks

    def get_graded_picks(
        self, year: int, league_id: int, week_condition=None, user: str = None
    ) -> list[dict]:
        """
        Every graded pick for a league-season, as flat rows with `pick_status`
        and `score` attached.

        This is the single source of grading. Grading the same picks twice in
        two places is how two views of them drift apart.

        Only concluded games are returned -- the join requires both scores -- so
        an unbounded week means "everything played so far" without the caller
        having to know which week that is.

        :param year:
        :param league_id: the league whose picks to return
        :param week_condition: a peewee expression over the week, so callers can
            ask for one week or every week up to one. `None` asks for the whole
            season.
        :param user: restrict to a single player
        """
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )

        conditions = [
            _season.year == year,
            _pick.league_season == league_season.id,
            _game_result.home_score.is_null(False),  # Ensure the game has concluded
            _game_result.away_score.is_null(False),  # Ensure the game has concluded
        ]
        if week_condition is not None:
            conditions.append(week_condition)
        if user:
            conditions.append(_user.username == user)

        return self._grade(self._graded_picks_query(conditions))

    def get_graded_picks_for_seasons(self, league_season_ids: list[int]) -> list[dict]:
        """
        Every graded pick across several of a league's seasons, in one query.

        The league history needs each season's standings at once. Asking per
        season meant a query -- and a Lambda invocation -- per year, growing by
        one every season the league survives. Rows carry their `year`, so the
        caller groups what comes back rather than asking again.
        """
        if not league_season_ids:
            return []

        return self._grade(
            self._graded_picks_query(
                [
                    _pick.league_season.in_(list(league_season_ids)),
                    _game_result.home_score.is_null(False),
                    _game_result.away_score.is_null(False),
                ]
            )
        )

    async def _get_pick_results(
        self, year: int, week_condition, league_id: int, user: str = None
    ) -> list[UserPickResultsDto]:
        """
        get list of all picks filtered by league, user and week, grouped by
        player and ranked

        :param year:
        :param week_condition:
        :param league_id: the league whose picks to return
        :param user:
        :return:
        """
        picks = self.get_graded_picks(
            year=year, week_condition=week_condition, league_id=league_id, user=user
        )

        user_results = {}
        for pick in picks:
            self.logger.debug(f"Processing pick: {pick}")

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
                        abbreviation=pick["selected_team_abbreviation"],
                        thumbnail=pick["selected_team_thumbnail"],
                        primary_color=pick["selected_team_primary_color"],
                        secondary_color=pick["selected_team_secondary_color"],
                    ),
                    confidence=pick["confidence"],
                    spread_value=pick["spread_value"],
                    status=pick["status"],
                    score=pick["score"],
                    pick_status=pick["pick_status"],
                    week=pick["week_number"],
                )
            )
            user_results[pick["username"]]["total_score"] += pick["score"]

        self.logger.info(f"Processed results for users: {list(user_results.keys())}")
        sorted_results = sorted(
            user_results.values(), key=lambda x: x["total_score"], reverse=True
        )
        for rank, result in enumerate(sorted_results, start=1):
            result["rank"] = rank

        return [UserPickResultsDto(**result) for result in sorted_results]

    def get_graded_picks_for_week(
        self, year: int, week: int, league_id: int
    ) -> list[dict]:
        """Graded picks for a single week -- the raw rows the week stats
        aggregate by game."""
        return self.get_graded_picks(
            year=year,
            week_condition=(_week_model.week_number == week),
            league_id=league_id,
        )

    def get_graded_picks_through_week(
        self, year: int, week: int, league_id: int
    ) -> list[dict]:
        """
        Graded picks from week one through `week` -- what a standing is the sum
        of. Exists so the week bound stays a peewee expression in this module
        rather than something every caller has to build.
        """
        return self.get_graded_picks(
            year=year,
            week_condition=(_week_model.week_number <= week),
            league_id=league_id,
        )

    async def get_user_pick_results(
        self, year: int, week: int, league_id: int, user: str = None
    ) -> list[UserPickResultsDto]:
        week_condition = _week_model.week_number == week
        return await self._get_pick_results(
            year, week_condition, league_id=league_id, user=user
        )

    async def get_season_pick_results(
        self, year: int, league_id: int, user: str = None
    ) -> list[UserPickResultsDto]:
        """
        Every graded pick of a season in one answer.

        This exists because the profile's team counts previously asked
        `user-picks` once per week and stitched the answers together -- up to
        eighteen requests, each its own cold start, to fill one card. The query
        underneath is the same one a single week runs, without the week bound.
        """
        return await self._get_pick_results(
            year, None, league_id=league_id, user=user
        )

    async def get_pick_history_for_year(
        self, year: int, week: int, league_id: int, user: str = None
    ) -> list[UserPickResultsDto]:
        return await self._get_pick_results(
            year=year,
            week_condition=_week_model.week_number <= week,
            league_id=league_id,
            user=user,
        )

    async def _get_week_results_task(
        self, year: int, week: int, league_id: int, user: str
    ):
        week_condition = _week_model.week_number == week
        results = await self._get_pick_results(
            year, week_condition, league_id=league_id, user=user
        )
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
