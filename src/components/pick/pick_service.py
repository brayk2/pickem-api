from src.components.pick.pick_models import (
    PickStatus,
    SubmitPicksRequestDto,
    PickDto,
    UserPicksDto,
    TeamDto,
)
from src.components.results.results_dto import MatchupDto
from src.config.base_service import BaseService
from src.models.new_db_models import (
    GameModel,
    PickModel,
    UserModel,
    WeekModel,
    SeasonModel,
    GameResultModel,
)
from peewee import DoesNotExist
from src.components.pick.pick_exceptions import (
    InvalidGameIDException,
    InvalidTeamIDException,
    InvalidSeasonException,
    InvalidWeekException,
    LockedPickException,
    InvalidGameWeekException,
)
from src.util.injection import dependency


@dependency
class PickService(BaseService):
    """
    Service class for handling operations related to picks in the PickEm application.
    """

    def validate_picks(self, picks_data: SubmitPicksRequestDto) -> None:
        """
        Validates the picks provided by the user, ensuring that all game IDs and team IDs are valid.

        :param picks_data: The picks submitted by the user.
        :raises InvalidGameIDException: If one or more game IDs are invalid.
        :raises InvalidTeamIDException: If a team ID is invalid for a specific game.
        """
        self.logger.info(f"Validating picks: {picks_data}")

        game_ids = [pick.game_id for pick in picks_data.picks]

        # Fetch all relevant games
        games = GameModel.select().where(GameModel.id << game_ids)
        if len(games) != len(game_ids):
            raise InvalidGameIDException("One or more game IDs are invalid.")

        # Validate each pick
        for pick in picks_data.picks:
            try:
                game = GameModel.get_by_id(pick.game_id)
                if (
                    pick.team_id != game.home_team.id
                    and pick.team_id != game.away_team.id
                ):
                    raise InvalidTeamIDException(
                        f"Team ID {pick.team_id} is not valid for Game ID {pick.game_id}."
                    )
            except DoesNotExist:
                raise InvalidGameIDException(f"Game ID {pick.game_id} does not exist.")

    def create_or_update_picks(
        self, picks_data: SubmitPicksRequestDto, user: UserModel, status: PickStatus
    ) -> None:
        """
        Creates new picks or updates existing picks for the user in the database with the given status.

        :param picks_data: The picks submitted by the user.
        :param user: The user submitting the picks.
        :param status: The status to apply to the picks.
        """
        with PickModel._meta.database.atomic():
            for pick in picks_data.picks:
                existing_pick = PickModel.get_or_none(
                    (PickModel.user_id == user.id) & (PickModel.game_id == pick.game_id)
                )

                if existing_pick:
                    # Ensure the fields are updated correctly
                    existing_pick.team_id = pick.team_id
                    existing_pick.spread_value = pick.spread_value
                    existing_pick.confidence = pick.confidence
                    existing_pick.status = status
                    existing_pick.save()
                    self.logger.info(
                        f"Pick updated for game ID {pick.game_id} "
                        f"and user ID {user.id}"
                    )
                else:
                    PickModel.create(
                        user=user,
                        game=pick.game_id,
                        team=pick.team_id,
                        spread_value=pick.spread_value,
                        confidence=pick.confidence,
                        status=status,
                    )
                    self.logger.info(
                        f"Pick created for game ID {pick.game_id} "
                        f"and user ID {user.id}"
                    )

    async def submit_picks(
        self, pick_data: SubmitPicksRequestDto, user: UserModel
    ) -> PickStatus:
        """
        Validates, creates or updates picks, ensures the correct status is set,
        and removes any picks that were not included in the submission for the same week.

        :param pick_data: The picks submitted by the user.
        :param user: The user submitting the picks.
        :return: The status of the submitted picks.
        :raises LockedPickException: If a user attempts to remove a locked pick.
        :raises InvalidGameWeekException: If any pick's game does not belong to the specified year and week.
        """
        self.logger.info(
            f"attempting to submit picks {pick_data} for user {user.username}"
        )

        # Validate picks
        self.validate_picks(pick_data)

        # Determine the overall status based on the length of picks
        new_status = (
            PickStatus.Submitted if len(pick_data.picks) >= 5 else PickStatus.Saved
        )

        # Get the game IDs from the submitted picks
        submitted_game_ids = [pick.game_id for pick in pick_data.picks]

        # Validate that all games are in the specified year and week
        games = GameModel.select().where(GameModel.id << submitted_game_ids)
        for game in games:
            if (
                game.season.year != pick_data.year
                or game.week.week_number != pick_data.week
            ):
                raise InvalidGameWeekException(
                    game_id=game.id,
                    expected_year=pick_data.year,
                    expected_week=pick_data.week,
                )

        # Fetch existing picks that are from the same week and year but not in the current submission
        existing_picks = (
            PickModel.select()
            .join(GameModel, on=(PickModel.game == GameModel.id))
            .join(WeekModel, on=(GameModel.week == WeekModel.id))
            .join(SeasonModel, on=(GameModel.season == SeasonModel.id))
            .where(
                (PickModel.user_id == user.id)
                & (WeekModel.week_number == pick_data.week)
                & (SeasonModel.year == pick_data.year)
                & ~(PickModel.game_id << submitted_game_ids)
            )
        )

        # Check if any of the existing picks are locked
        for pick in existing_picks:
            if pick.status == PickStatus.Locked:
                raise LockedPickException(
                    f"Pick for game ID {pick.game_id} is locked and cannot be removed."
                )

        # Delete picks that are from the same week and year but not in the current submission (only if they are not locked)
        PickModel.delete().where(
            (PickModel.user_id == user.id)
            & (PickModel.game_id.not_in(submitted_game_ids))
            & (
                PickModel.game.in_(
                    GameModel.select(GameModel.id)
                    .join(WeekModel)
                    .join(SeasonModel)
                    .where(
                        (WeekModel.week_number == pick_data.week)
                        & (SeasonModel.year == pick_data.year)
                    )
                )
            )
        ).execute()

        # Create or update picks with the appropriate status
        self.create_or_update_picks(picks_data=pick_data, user=user, status=new_status)

        return new_status

    def get_user_picks_for_week(
        self, user: UserModel, year: int, week_number: int
    ) -> UserPicksDto:
        # Fetch the season based on the year
        try:
            season = SeasonModel.get(SeasonModel.year == year)
        except DoesNotExist:
            self.logger.error(f"Season with year {year} does not exist.")
            raise InvalidSeasonException(f"Season with year {year} does not exist.")

        # Fetch the week based on the season and week number
        try:
            week = WeekModel.get(
                (WeekModel.season == season) & (WeekModel.week_number == week_number)
            )
        except DoesNotExist:
            self.logger.error(f"Week {week_number} does not exist for year {year}.")
            raise InvalidWeekException(
                f"Week {week_number} does not exist for year {year}."
            )

        # Fetch all games for that season and week
        games = GameModel.select().where(
            (GameModel.season == season) & (GameModel.week == week)
        )

        # Fetch the user's picks for those games
        picks = PickModel.select().where(
            (PickModel.user == user.id) & (PickModel.game << games)
        )

        filtered_games = [pick.game for pick in picks]
        results = GameResultModel.select().where(
            (GameResultModel.game << filtered_games)
        )
        results_lookup = {result["game"]: result for result in results.dicts()}

        pick_dto_list = []
        for pick in picks:
            game = pick.game
            game_results = results_lookup.get(game.id, {})

            # Manually map fields to MatchupDto
            matchup_dto = MatchupDto(
                game_id=game.id,
                home_team=TeamDto(
                    team_id=game.home_team.id,
                    team_city=game.home_team.city,
                    team_name=game.home_team.name,
                    thumbnail=game.home_team.thumbnail,
                    abbreviation=game.home_team.abbreviation,
                ),
                away_team=TeamDto(
                    team_id=game.away_team.id,
                    team_city=game.away_team.city,
                    team_name=game.away_team.name,
                    thumbnail=game.away_team.thumbnail,
                    abbreviation=game.away_team.abbreviation,
                ),
                start_time=game.start_time,
                start_date=game.start_date,
                # Add other necessary fields here based on your MatchupDto structure
                lines={
                    game.home_team.name: f"{pick.spread_value:.1f}".rstrip("0").rstrip(
                        "."
                    ),
                    game.away_team.name: f"{pick.spread_value:.1f}".rstrip("0").rstrip(
                        "."
                    ),
                },
                results=(
                    {
                        game.home_team.name: game_results.get("home_score"),
                        game.away_team.name: game_results.get("away_score"),
                    }
                    if game_results
                    else None
                ),
            )

            # Construct the PickDto
            pick_dto = PickDto(
                id=pick.id,
                game=matchup_dto,
                team=TeamDto(
                    team_id=pick.team.id,
                    team_name=pick.team.name,
                    team_city=pick.team.city,
                    thumbnail=pick.team.thumbnail,
                    abbreviation=pick.team.abbreviation,
                ),
                spread_value=float(pick.spread_value),
                confidence=pick.confidence,
                status=pick.status,
            )

            pick_dto_list.append(pick_dto)

        # Determine the overall status based on the number of picks
        if not pick_dto_list:
            overall_status = PickStatus.New
        elif len(pick_dto_list) < 5:
            overall_status = PickStatus.Saved
        else:
            overall_status = PickStatus.Submitted

        return UserPicksDto(picks=pick_dto_list, status=overall_status)
