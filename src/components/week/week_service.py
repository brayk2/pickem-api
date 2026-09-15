from peewee import JOIN, DoesNotExist, fn

from src.components.week.week_exceptions import WeekNotFoundException
from src.config.base_service import BaseService
from src.models.db_models import (
    GameModel,
    GameResultModel,
    SeasonModel,
    WeekModel,
)
from src.util.injection import dependency

# `week.completed` has two authors: the scraper, which marks a week finished
# once every game in it has a final score, and an admin who needs to override
# that. They would fight -- an admin holding a week back would be re-completed
# by the next scrape -- so the sync leaves any week an admin has touched alone.
# `updated_by` is the record of who wrote the flag last.
SYNC_ACTOR = "week_sync"
ADMIN_ACTOR_PREFIX = "admin:"


def admin_actor(username: str) -> str:
    return f"{ADMIN_ACTOR_PREFIX}{username}"


@dependency
class WeekService(BaseService):
    """
    Owns `week.completed`: whether a week is finished and its end-of-week
    statistics can be published.

    Completion is stored rather than derived on read so it can be overridden.
    The common case is automatic (see sync_season_completion, which the scraper
    calls after loading results), but a commissioner who spots a bad score needs
    to be able to hold a week back, and someone waiting on an abandoned game
    needs to be able to release one early.
    """

    def get_week(self, year: int, week: int) -> WeekModel:
        try:
            return (
                WeekModel.select()
                .join(SeasonModel, on=(WeekModel.season == SeasonModel.id))
                .where((SeasonModel.year == year) & (WeekModel.week_number == week))
                .get()
            )
        except DoesNotExist:
            self.logger.error(f"Week {week} of season {year} not found")
            raise WeekNotFoundException(year=year, week=week)

    def is_complete(self, year: int, week: int) -> bool:
        """
        Whether the week is finished. A week that is not on the schedule at all
        is not complete -- callers gate on this to decide whether to publish
        week statistics, and an unknown week has none.
        """
        model = (
            WeekModel.select(WeekModel.completed)
            .join(SeasonModel, on=(WeekModel.season == SeasonModel.id))
            .where((SeasonModel.year == year) & (WeekModel.week_number == week))
            .first()
        )
        return bool(model and model.completed)

    def set_completion(self, year: int, week: int, completed: bool, actor: str) -> bool:
        """
        Force a week's completion state. Stamps `updated_by` with the admin who
        did it so the automatic sync stops overwriting the week.
        """
        model = self.get_week(year=year, week=week)
        WeekModel.update(completed=completed, updated_by=admin_actor(actor)).where(
            WeekModel.id == model.id
        ).execute()

        self.logger.info(
            f"{actor} set week {week} of {year} completed={completed} (was {model.completed})"
        )
        return completed

    def sync_season_completion(self, year: int) -> list[int]:
        """
        Mark every week of `year` whose games all have final scores complete.

        Only ever promotes a week to complete: an admin who deliberately
        un-completed a week would otherwise have it flipped back by the next
        scrape. Returns the week numbers that changed.
        """
        rows = (
            WeekModel.select(
                WeekModel.id,
                WeekModel.week_number,
                fn.COUNT(GameModel.id.distinct()).alias("game_count"),
                fn.COUNT(GameResultModel.id.distinct()).alias("result_count"),
            )
            .join(SeasonModel, on=(WeekModel.season == SeasonModel.id))
            .switch(WeekModel)
            .join(GameModel, JOIN.LEFT_OUTER, on=(GameModel.week == WeekModel.id))
            .join(
                GameResultModel,
                JOIN.LEFT_OUTER,
                on=(
                    (GameResultModel.game == GameModel.id)
                    & GameResultModel.home_score.is_null(False)
                    & GameResultModel.away_score.is_null(False)
                ),
            )
            .where(
                (SeasonModel.year == year)
                & (WeekModel.completed == False)  # noqa: E712 -- peewee expression
                & (
                    WeekModel.updated_by.is_null(True)
                    | ~WeekModel.updated_by.startswith(ADMIN_ACTOR_PREFIX)
                )
            )
            .group_by(WeekModel.id, WeekModel.week_number)
            .dicts()
        )

        # A week with no games is unscheduled, not finished, so game_count > 0.
        finished = [
            row
            for row in rows
            if row["game_count"] and row["game_count"] == row["result_count"]
        ]
        if not finished:
            self.logger.info(f"No newly completed weeks in {year}")
            return []

        week_ids = [row["id"] for row in finished]
        WeekModel.update(completed=True, updated_by=SYNC_ACTOR).where(
            WeekModel.id.in_(week_ids)
        ).execute()

        week_numbers = sorted(row["week_number"] for row in finished)
        self.logger.info(f"Marked weeks {week_numbers} of {year} complete")
        return week_numbers
