from peewee import fn

from src.components.league.league_service import LeagueService
from src.components.results.results_service import ResultsService
from src.components.standings.standings_models import (
    LeagueSeasonStandingsDto,
    StandingsDto,
    StandingsHistoryDto,
    TeamSeasonStatsDto,
    UserHistoryDto,
)
from src.components.standings.team_season_stats import build_team_season_stats
from src.models.db_models import SeasonModel, WeekModel
from src.config.base_service import BaseService
from src.config.logger import Logger
from src.util.injection import dependency, inject

# A covered pick is a correct pick, a push half of one, a miss none. This is
# the "record" sense of correct, distinct from the score, which weights the
# same outcomes by the confidence staked on them.
CORRECT_VALUES = {"COVERED": 1.0, "PUSHED": 0.5, "FAILED": 0.0}


@dependency
class StandingsService(BaseService):
    @inject
    def __init__(
        self,
        results_service: ResultsService,
        league_service: LeagueService,
        logger: Logger,
    ):
        """
        Initializes the StandingsService
        """
        self.results_service = results_service
        self.league_service = league_service
        self.logger = logger

    @staticmethod
    def seed_totals(usernames) -> dict[str, dict]:
        """
        A zeroed row for every member of the season.

        Seeded from the roster rather than from pick activity, so a member who
        has missed every week so far still appears at zero rather than
        vanishing from the table.
        """
        return {
            username: {"score": 0.0, "correct": 0.0, "total": 0}
            for username in usernames
        }

    @staticmethod
    def accumulate(totals: dict[str, dict], row: dict) -> None:
        """Fold one graded pick into a player's running totals."""
        entry = totals.get(row["username"])
        if entry is None:
            # A pick from someone no longer on the roster still counts: the
            # season happened.
            entry = totals[row["username"]] = {"score": 0.0, "correct": 0.0, "total": 0}

        entry["score"] += row["score"] or 0.0
        entry["correct"] += CORRECT_VALUES.get(row["pick_status"], 0.0)
        entry["total"] += 1

    @staticmethod
    def rank(totals: dict[str, dict]) -> list[StandingsDto]:
        """Totals to a ranked table, highest score first."""
        standings = [
            StandingsDto(
                username=username,
                rank=0,  # assigned below, once sorted
                correct_picks=entry["correct"],
                total_picks=entry["total"],
                score=entry["score"],
            )
            for username, entry in totals.items()
        ]

        standings.sort(key=lambda standing: standing.score, reverse=True)
        for position, standing in enumerate(standings, start=1):
            standing.rank = position

        return standings

    def season_members(self, league_id: int, year: int) -> list[str]:
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )
        return [
            member.username
            for member in self.league_service.list_members(league_season=league_season)
        ]

    def build_standings(self, rows: list[dict], usernames) -> list[StandingsDto]:
        """A ranked table from already-graded rows."""
        totals = self.seed_totals(usernames)
        for row in rows:
            self.accumulate(totals, row)
        return self.rank(totals)

    async def get_standings_for_week(
        self, year: int, week: int, league_id: int
    ) -> list[StandingsDto]:
        """
        The table as it stood after `week`, counting everything from week one.

        Reads the flat graded rows rather than the grouped result DTOs. A
        standing is five numbers per player, and building a PickDto -- with its
        nested team, thumbnail and colours -- for each of a season's ~1,080
        picks to produce them was a thousand objects constructed and discarded
        per request.
        """
        self.logger.info(
            f"Fetching standings for league {league_id}, year {year} up to week {week}"
        )

        usernames = self.season_members(league_id=league_id, year=year)
        rows = self.results_service.get_graded_picks_through_week(
            year=year, week=week, league_id=league_id
        )

        standings = self.build_standings(rows, usernames)
        self.logger.info(f"Standings calculated for week {week} of year {year}")
        return standings

    async def get_team_season_stats(
        self, year: int, week: int, league_id: int
    ) -> TeamSeasonStatsDto:
        """
        The league's season so far team by team, through `week`.

        The same graded rows as the table beside it, grouped by the team picked
        rather than by the player -- no second grading. The season's games come
        alongside so each team's own weekly form covers games nobody picked.
        """
        self.logger.info(
            f"Fetching team season stats for league {league_id}, {year} through week {week}"
        )
        rows = self.results_service.get_graded_picks_through_week(
            year=year, week=week, league_id=league_id
        )
        games = self.results_service.get_games_through_week(year=year, week=week)
        return build_team_season_stats(
            rows, year=year, through_week=week, games=games
        )

    async def get_standings_history(
        self, year: int, week: int, league_id: int
    ) -> StandingsHistoryDto:
        """
        Every week's table in one answer, for the movement chart.

        This used to call get_standings_for_week once per week, and each of
        those graded weeks one through w -- so asking for week 18 graded 60
        picks, then 120, then 180, all the way up: ~10,260 picks and 54 queries
        to produce 216 rows, and quadratic in the week number, meaning it was
        at its worst in January.

        A standing is a running total, so the season is graded once and the
        weeks are accumulated in order. Same answer, one pass.
        """
        weeks = list(range(1, week + 1))
        self.logger.info(f"Defined weeks as {weeks}")

        usernames = self.season_members(league_id=league_id, year=year)
        rows = self.results_service.get_graded_picks_through_week(
            year=year, week=week, league_id=league_id
        )

        by_week: dict[int, list[dict]] = {w: [] for w in weeks}
        for row in rows:
            # A row outside the asked-for range cannot happen, but a week with
            # no graded picks must still produce a table -- everyone holds
            # their score.
            by_week.setdefault(row["week_number"], []).append(row)

        totals = self.seed_totals(usernames)
        user_histories: dict[str, UserHistoryDto] = {}

        for week_number in weeks:
            for row in by_week.get(week_number, []):
                self.accumulate(totals, row)

            for standing in self.rank(totals):
                history = user_histories.get(standing.username)
                if history is None:
                    history = user_histories[standing.username] = UserHistoryDto(
                        username=standing.username, ranks=[], scores=[], pcts=[]
                    )

                history.ranks.append(standing.rank)
                history.scores.append(standing.score)
                history.pcts.append(
                    (standing.correct_picks / standing.total_picks)
                    if standing.total_picks > 0
                    else 0.0
                )

        return StandingsHistoryDto(
            year=year,
            weeks=weeks,
            users=list(user_histories.values()),
            completed=self.completed_weeks(year=year, through_week=week),
        )

    @staticmethod
    def completed_weeks(year: int, through_week: int) -> list[int]:
        """The season's finished weeks, up to and including `through_week`."""
        return [
            row["week_number"]
            for row in (
                WeekModel.select(WeekModel.week_number)
                .join(SeasonModel, on=(WeekModel.season == SeasonModel.id))
                .where(
                    (SeasonModel.year == year)
                    & (WeekModel.week_number <= through_week)
                    & (WeekModel.completed == True)  # noqa: E712 -- peewee expression
                )
                .order_by(WeekModel.week_number)
                .dicts()
            )
        ]

    def finished_years(self, years: list[int]) -> set[int]:
        """
        Of the years asked about, those whose every week is marked complete.

        A season still being played has a week that is not done, so it has a
        leader rather than a champion. A season with no weeks at all is not
        finished either -- nothing has happened to finish it -- and falls out
        of this set by being absent from the grouping.
        """
        if not years:
            return set()

        return {
            row["year"]
            for row in (
                WeekModel.select(
                    SeasonModel.year.alias("year"),
                    fn.BOOL_AND(WeekModel.completed).alias("all_done"),
                )
                .join(SeasonModel, on=(WeekModel.season == SeasonModel.id))
                .where(SeasonModel.year.in_(list(years)))
                .group_by(SeasonModel.year)
                .dicts()
            )
            if row["all_done"]
        }

    def get_league_history(self, league_id: int) -> list[LeagueSeasonStandingsDto]:
        """
        Every season the league has played, each with its final table.

        This lives here rather than on LeagueService because it is standings:
        it needs the grader and the ranking, and LeagueService cannot reach
        either without importing what already imports it.

        The point of the endpoint is that the work does not grow with the
        league's age. Building this in the client meant a standings request per
        season -- so a query, a grading pass and a Lambda invocation for every
        year, one more every autumn, forever. Here it is four queries whether
        the league is two years old or twenty.
        """
        seasons = self.league_service.list_league_seasons(league_id=league_id)
        if not seasons:
            return []

        season_ids = [season.id for season in seasons]
        rows = self.results_service.get_graded_picks_for_seasons(season_ids)
        rosters = self.league_service.list_members_by_season(season_ids)
        finished = self.finished_years([season.year for season in seasons])

        by_year: dict[int, list[dict]] = {}
        for row in rows:
            by_year.setdefault(row["year"], []).append(row)

        history = []
        for season in seasons:
            usernames = [member.username for member in rosters.get(season.id, [])]
            standings = self.build_standings(by_year.get(season.year, []), usernames)

            # A season nobody has scored in has no leader: every member is
            # seeded at zero, so the top row would just be whoever sorted
            # first.
            leader = standings[0] if standings and standings[0].score > 0 else None

            history.append(
                LeagueSeasonStandingsDto(
                    year=season.year,
                    in_progress=season.year not in finished,
                    player_count=len(usernames),
                    leader=leader,
                    standings=standings,
                )
            )

        return sorted(history, key=lambda season: season.year, reverse=True)
