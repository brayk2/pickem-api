import asyncio

from peewee import JOIN

from src.components.results.results_models import (
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
    SpreadModel,
    WeekModel,
)
from src.components.league.league_service import LeagueService
from src.components.season.season_exceptions import (
    WeekNotSetException,
    YearNotSetException,
)
from src.components.season.season_service import SeasonService
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
_home_line = SpreadModel.alias()
_away_line = SpreadModel.alias()

# The book the league's lines come from.
HOUSE_BOOK = "DraftKings"

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


def crowd_counts(rows: list[dict], username: str) -> dict[int, tuple[int, int]]:
    """
    For each of one player's picks, how many other players took the same side
    of that game and how many took the other side, keyed by pick id.

    `rows` are the league's graded picks for the season, the player's among
    them. Nobody is counted against themselves.
    """
    sides: dict[int, dict[int, int]] = {}
    for row in rows:
        if row["username"] == username:
            continue
        game = sides.setdefault(row["game_id"], {})
        game[row["selected_team_id"]] = game.get(row["selected_team_id"], 0) + 1

    counts = {}
    for row in rows:
        if row["username"] != username:
            continue
        game = sides.get(row["game_id"], {})
        same = game.get(row["selected_team_id"], 0)
        counts[row["id"]] = (same, sum(game.values()) - same)
    return counts


@dependency
class ResultsService(BaseService):
    @inject
    def __init__(self, league_service: LeagueService, season_service: SeasonService):
        super().__init__()
        self.league_service = league_service
        self.season_service = season_service

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

    def get_games_through_week(self, year: int, week: int) -> list[dict]:
        """
        Every game of the season from week one through `week`, picked or not,
        with its score (None until final) and the house line on each side.

        The graded picks only reach games somebody picked. A team's own record
        against the spread needs the rest too, and which weeks it had no game
        at all -- its bye.
        """
        query = (
            _game.select(
                _game.id.alias("game_id"),
                _week_model.week_number,
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
                _home_line.spread_value.alias("home_team_line"),
                _away_line.spread_value.alias("away_team_line"),
            )
            .join(_home_team, on=(_game.home_team == _home_team.id))
            .join(_away_team, on=(_game.away_team == _away_team.id))
            .join(_season, on=(_game.season == _season.id))
            .join(_week_model, on=(_game.week == _week_model.id))
            .join(_game_result, JOIN.LEFT_OUTER, on=(_game_result.game == _game.id))
            .join(
                _home_line,
                JOIN.LEFT_OUTER,
                on=(
                    (_home_line.game == _game.id)
                    & (_home_line.team == _game.home_team)
                    & (_home_line.bookmaker == HOUSE_BOOK)
                ),
            )
            .join(
                _away_line,
                JOIN.LEFT_OUTER,
                on=(
                    (_away_line.game == _game.id)
                    & (_away_line.team == _game.away_team)
                    & (_away_line.bookmaker == HOUSE_BOOK)
                ),
            )
            .where(_season.year == year, _week_model.week_number <= week)
            .order_by(_week_model.week_number)
        )
        return list(query.dicts())

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

    def week_is_open(self, year: int, week: int) -> bool:
        """
        Whether a week has opened, and so whether who-has-submitted may be told.

        The week flips on the Thursday 6am rollover that pulls the lines, which
        is also when the pick window opens, so this is `week <= current_week` in
        the current season rather than anything to do with kickoff. Nudging
        somebody who has not picked is only useful before the deadline, and a
        confidence level on its own gives away nothing about a selection.

        A missing current week or year means the season has not been set up.
        That is not a reason to fail a results page, so it reads as not open --
        the conservative direction, since it withholds rather than reveals.
        """
        try:
            current = self.season_service.get_current_week_and_year()
        except (WeekNotSetException, YearNotSetException):
            self.logger.warning("Current week/year unset; treating week as unopened")
            return False

        if int(current["year"]) != int(year):
            # A past season is entirely open; a future one entirely closed.
            return int(year) < int(current["year"])

        return int(week) <= int(current["week"])

    def get_submitted_confidences(
        self, year: int, week: int, league_id: int
    ) -> dict[str, list[int]]:
        """
        Which confidence levels each player has staked but not yet had graded,
        as {username: [5, 3]}.

        This is what lets the results page say "Johnny has his 5 and his 3 in"
        while the picks themselves stay hidden, and why it is a separate query
        rather than a filter over the graded rows: it selects the username and
        the confidence and *nothing else*. There is no team, line or score in
        the result set to leak, so no later edit to this file can widen it into
        one by accident. The response DTO has nowhere to put a team either.

        The predicate is the exact complement of the graded query's -- a pick
        whose game has no result row, or has one with a missing score -- so
        every submitted pick is either graded or pending, never both and never
        neither.
        """
        if not self.week_is_open(year=year, week=week):
            return {}

        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )

        query = (
            _pick.select(_user.username, _pick.confidence)
            .join(_user, on=(_pick.user == _user.id))
            .join(_game, on=(_pick.game == _game.id))
            .join(_season, on=(_game.season == _season.id))
            .join(_week_model, on=(_game.week == _week_model.id))
            # LEFT OUTER because the rows wanted here are the ones the graded
            # query's inner join throws away: games with no result at all.
            .join(_game_result, JOIN.LEFT_OUTER, on=(_game_result.game == _game.id))
            .where(
                _season.year == year,
                _week_model.week_number == week,
                _pick.league_season == league_season.id,
                (
                    _game_result.id.is_null()
                    | _game_result.home_score.is_null()
                    | _game_result.away_score.is_null()
                ),
            )
            .order_by(_pick.confidence.desc())
        )

        self.logger.info(f"Pending-confidence query: {query.sql()}")

        pending: dict[str, list[int]] = {}
        for row in query.dicts():
            pending.setdefault(row["username"], []).append(row["confidence"])

        return pending

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

    async def get_user_week_results(
        self, year: int, week: int, league_id: int, username: str
    ) -> UserPickResultsDto:
        """One player's graded picks for a week, or an empty row if there are none."""
        self.logger.info(f"Getting user pick results for year {year} and week {week}")
        if picks := await self.get_user_pick_results(
            year, week, league_id=league_id, user=username
        ):
            return picks[0]
        return UserPickResultsDto(username=username, picks=[], total_score=0, rank=None)

    async def get_user_season_results(
        self, year: int, league_id: int, username: str
    ) -> UserPickResultsDto:
        """
        One player's graded picks for the whole season, or an empty row.

        `rank` is deliberately null. The score here is a season total for one
        player, with nobody to rank them against -- returning the 1 that ranking a
        single-row result produces would read as a league position.
        """
        self.logger.info(f"Getting season pick results for league {league_id}, {year}")
        if results := await self.get_season_pick_results(
            year, league_id=league_id, user=username
        ):
            season = results[0]
            season.rank = None

            # The whole league's graded picks, to say how everyone else played
            # each of this player's games.
            counts = crowd_counts(
                self.get_graded_picks(year=year, league_id=league_id),
                username=username,
            )
            for pick in season.picks:
                same, other = counts.get(pick.id, (0, 0))
                pick.same_side = same
                pick.other_side = other
            return season
        return UserPickResultsDto(username=username, picks=[], total_score=0, rank=None)

    async def get_pick_history_for_year(
        self, year: int, week: int, league_id: int, user: str = None
    ) -> list[UserPickResultsDto]:
        self.logger.info(f"Getting pick history for year {year} through week {week}")
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

    async def get_league_week_results(
        self, year: int, week: int, league_id: int
    ) -> list[UserPickResultsDto]:
        """
        The week's table with every player on it, whether they picked or not.

        Previously this was built from the graded picks alone, which meant a
        player with nothing graded was not in the answer at all -- so the page
        could not count the league, and "has not submitted" and "submitted,
        still playing" looked the same: an absent row either way.

        Everyone on the season's roster gets a row now. Three states fall out
        per confidence slot: graded picks arrive in `picks` with a status,
        staked-but-ungraded ones as numbers in `submitted_confidences`, and a
        slot in neither was never filled.
        """
        self.logger.info(f"Getting league pick results for year {year} and week {week}")
        results = await self.get_user_pick_results(year, week, league_id=league_id)
        scored = {result.username: result for result in results}

        submitted = self.get_submitted_confidences(
            year=year, week=week, league_id=league_id
        )
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )
        members = self.league_service.list_members(league_season=league_season)

        # Roster first, then anyone who has a pick but has since left it: a
        # season that was played happened, whoever is on the roster now.
        usernames = {member.username for member in members}
        usernames.update(scored)
        usernames.update(submitted)

        rows = [
            UserPickResultsDto(
                username=username,
                picks=scored[username].picks if username in scored else [],
                total_score=(
                    scored[username].total_score if username in scored else 0.0
                ),
                submitted_confidences=submitted.get(username, []),
            )
            for username in sorted(usernames)
        ]

        # Sorted by name above and by score here, and Python's sort is stable,
        # so players on the same score come out alphabetically rather than in
        # whatever order the set iterated. Ranking is otherwise untouched --
        # still positional, ties still not shared.
        rows.sort(key=lambda row: row.total_score, reverse=True)
        for position, row in enumerate(rows, start=1):
            row.rank = position

        return rows

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
