import asyncio

from src.components.results.results_dto import UserPickResultsDto, PickDto
from src.components.league.league_service import LeagueService
from src.components.results.results_service import ResultsService
from src.components.standings.standings_dtos import (
    StandingsDto,
    StandingsHistoryDto,
    UserHistoryDto,
)
from src.config.base_service import BaseService
from src.config.logger import Logger
from src.util.injection import dependency, inject


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
    async def _calc_correct_picks(picks: list[PickDto]) -> float:
        status_scores = {
            "COVERED": 1,
            "PUSHED": 0.5,
            "FAILED": 0,
        }
        return sum(status_scores.get(pick.pick_status, 0) for pick in picks)

    @staticmethod
    async def _calc_total_picks(picks: list[PickDto]) -> int:
        return len(picks)

    @staticmethod
    async def _aggregate_scores(picks: list[PickDto]) -> int:
        return sum(pick.score for pick in picks if pick.score is not None)

    async def get_standings_for_week(
        self, year: int, week: int, league_id: int
    ) -> list[StandingsDto]:
        # Fetch user pick results up to the specified year and week
        self.logger.info(
            f"Fetching standings for league {league_id}, year {year} up to week {week}"
        )

        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )

        pick_results: list[UserPickResultsDto] = (
            await self.results_service.get_pick_history_for_year(
                year=year, week=week, league_id=league_id
            )
        )

        # Seed from the roster, not from pick activity, so a member who missed
        # every week so far still appears at zero rather than vanishing.
        user_aggregated_results = {
            member.username: {
                "picks": [],
                "total_score": 0,
                "correct_picks": 0,
                "total_picks": 0,
            }
            for member in self.league_service.list_members(league_season=league_season)
        }

        # Accumulate results across all weeks up to the specified week
        for user_picks in pick_results:
            username = user_picks.username
            if username not in user_aggregated_results:
                user_aggregated_results[username] = {
                    "picks": [],
                    "total_score": 0,
                    "correct_picks": 0,
                    "total_picks": 0,
                }

            # Extend the picks list with picks from this user for all weeks
            user_aggregated_results[username]["picks"].extend(user_picks.picks)

            # Aggregate scores, correct picks, and total picks
            user_aggregated_results[username][
                "total_score"
            ] += await self._aggregate_scores(user_picks.picks)
            user_aggregated_results[username][
                "correct_picks"
            ] += await self._calc_correct_picks(user_picks.picks)
            user_aggregated_results[username][
                "total_picks"
            ] += await self._calc_total_picks(user_picks.picks)

        # Calculate standings
        standings = []
        for username, data in user_aggregated_results.items():
            standings.append(
                StandingsDto(
                    username=username,
                    rank=0,  # To be calculated after sorting by score
                    correct_picks=data["correct_picks"],
                    total_picks=data["total_picks"],
                    score=data["total_score"],
                )
            )

        # Sort standings by score and assign ranks
        standings.sort(key=lambda x: x.score, reverse=True)
        for rank, standing in enumerate(standings, start=1):
            standing.rank = rank

        self.logger.info(f"Standings calculated for week {week} of year {year}")

        return standings

    async def get_standings_history(
        self, year: int, week: int, league_id: int
    ) -> StandingsHistoryDto:
        weeks = list(range(1, week + 1))
        self.logger.info(f"Defined weeks as {weeks}")

        semaphore = asyncio.Semaphore(10)  # Limit concurrency to 10 tasks at a time

        async def fetch_week_standings(w):
            async with semaphore:
                try:
                    standings = await self.get_standings_for_week(
                        year, w, league_id=league_id
                    )
                    return w, standings  # Return the week number along with standings
                except Exception as e:
                    self.logger.error(f"Error fetching standings for week {w}: {e}")
                    return w, []  # Return an empty list if an error occurs

        # Run all tasks concurrently
        standings_tasks = [fetch_week_standings(w) for w in weeks]
        all_weeks_standings = await asyncio.gather(*standings_tasks)

        user_histories: dict[str, UserHistoryDto] = {}

        # Process each week's standings
        for week_number, standings in all_weeks_standings:
            for standing in standings:
                if standing.username not in user_histories:
                    user_histories[standing.username] = UserHistoryDto(
                        username=standing.username,
                        ranks=[],
                        scores=[],
                        pcts=[],
                    )
                user_history = user_histories[standing.username]
                user_history.ranks.append(standing.rank)
                user_history.scores.append(standing.score)
                pct = (
                    (standing.correct_picks / standing.total_picks)
                    if standing.total_picks > 0
                    else 0.0
                )
                user_history.pcts.append(pct)

        return StandingsHistoryDto(
            year=year, weeks=weeks, users=list(user_histories.values())
        )
