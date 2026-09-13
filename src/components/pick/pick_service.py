from src.components.pick.kickoff import has_started
from src.components.pick.pick_models import (
    PickStatus,
    SubmitPicksRequestDto,
    PickDto,
    UserPicksDto,
    TeamDto,
)
from src.components.auth.auth_models import DecodedToken
from src.components.league.league_exceptions import (
    NotALeagueMemberException,
)
from src.components.league.league_service import LeagueService
from src.components.results.results_dto import MatchupDto
from src.config.base_service import BaseService
from src.models.db_models import (
    GameModel,
    PickModel,
    UserModel,
    WeekModel,
    SeasonModel,
    GameResultModel,
    LeagueSeasonModel,
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
from src.util.injection import dependency, inject


@dependency
class PickService(BaseService):
    """
    Service class for handling operations related to picks in the PickEm application.

    Every read and write is scoped to a league-season. The same user may play in
    several leagues in the same year, so user + game alone does not identify a pick.
    """

    @inject
    def __init__(self, league_service: LeagueService):
        self.league_service = league_service

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
        self,
        picks_data: SubmitPicksRequestDto,
        user: UserModel,
        status: PickStatus,
        league_season: LeagueSeasonModel,
    ) -> None:
        """
        Creates new picks or updates existing picks for the user in the database with the given status.

        :param picks_data: The picks submitted by the user.
        :param user: The user submitting the picks.
        :param status: The status to apply to the picks.
        :param league_season: The league-season these picks belong to.
        """
        with PickModel._meta.database.atomic():
            for pick in picks_data.picks:
                existing_pick = PickModel.get_or_none(
                    (PickModel.user_id == user.id)
                    & (PickModel.league_season_id == league_season.id)
                    & (PickModel.game_id == pick.game_id)
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
                        league_season=league_season,
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

    @staticmethod
    def _is_same_pick(existing: PickModel, submitted) -> bool:
        """Whether a submitted pick matches what is already stored."""
        return (
            existing.team_id == submitted.team_id
            and int(existing.confidence) == int(submitted.confidence)
            # spread_value is a DecimalField on one side and a float on the
            # other; compare at the two places the column actually stores.
            and round(float(existing.spread_value), 2)
            == round(float(submitted.spread_value), 2)
        )

    def _reject_changes_to_started_games(
        self,
        picks_data: SubmitPicksRequestDto,
        started_game_ids: list[int],
        existing_by_game: dict,
    ) -> None:
        """
        Server-side kickoff enforcement.

        The UI hides started games, but nothing stopped a direct API call from
        picking a game after it had begun -- and a timezone bug in the webapp
        made that reachable by accident for anyone west of US Eastern.
        """
        for pick in picks_data.picks:
            if pick.game_id not in started_game_ids:
                continue

            current = existing_by_game.get(pick.game_id)
            if current is not None and self._is_same_pick(current, pick):
                continue

            self.logger.warning(
                f"Rejected a pick for game {pick.game_id}, which has started"
            )
            raise LockedPickException(
                f"Game {pick.game_id} has already started; its pick can no longer be "
                f"set or changed."
            )

    async def submit_picks(
        self,
        pick_data: SubmitPicksRequestDto,
        user: UserModel,
        league_id: int,
        token: DecodedToken,
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
            f"attempting to submit picks {pick_data} for user {user.username} "
            f"in league {league_id}"
        )

        # Authorize from the token. The year lives in the request body, so this
        # cannot be a path-parameter dependency like the other league routes.
        if not (
            token.is_admin
            or token.is_member(league_id=league_id, year=pick_data.year)
        ):
            raise NotALeagueMemberException(
                username=user.username, league_id=league_id, year=pick_data.year
            )

        # Resolve the league-season the pick rows belong to
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=pick_data.year
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

        # Every game in the week, so a started game can be protected whether or
        # not the submission happens to mention it.
        week_games = list(
            GameModel.select()
            .join(WeekModel, on=(GameModel.week == WeekModel.id))
            .join(SeasonModel, on=(GameModel.season == SeasonModel.id))
            .where(
                (WeekModel.week_number == pick_data.week)
                & (SeasonModel.year == pick_data.year)
            )
        )
        started_game_ids = [game.id for game in week_games if has_started(game)]

        existing_picks = list(
            PickModel.select()
            .join(GameModel, on=(PickModel.game == GameModel.id))
            .join(WeekModel, on=(GameModel.week == WeekModel.id))
            .join(SeasonModel, on=(GameModel.season == SeasonModel.id))
            .where(
                (PickModel.user_id == user.id)
                & (PickModel.league_season_id == league_season.id)
                & (WeekModel.week_number == pick_data.week)
                & (SeasonModel.year == pick_data.year)
            )
        )
        existing_by_game = {pick.game_id: pick for pick in existing_picks}

        # A started game's pick is frozen. The client resubmits it unchanged as
        # part of the week's full slate, so an identical value is allowed
        # through; anything else is an attempt to pick after kickoff.
        self._reject_changes_to_started_games(
            picks_data=pick_data,
            started_game_ids=started_game_ids,
            existing_by_game=existing_by_game,
        )

        # Refuse to drop a pick whose game has started, however the submission
        # arrived -- omitting it would otherwise delete it below.
        for pick in existing_picks:
            if pick.game_id not in submitted_game_ids and (
                pick.game_id in started_game_ids
                or pick.status == PickStatus.Locked
            ):
                raise LockedPickException(
                    f"Pick for game ID {pick.game_id} is locked and cannot be removed."
                )

        # Delete picks from this week that were left out of the submission.
        PickModel.delete().where(
            (PickModel.user_id == user.id)
            & (PickModel.league_season_id == league_season.id)
            & (PickModel.game_id.not_in(submitted_game_ids + started_game_ids))
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
        self.create_or_update_picks(
            picks_data=pick_data,
            user=user,
            status=new_status,
            league_season=league_season,
        )

        return new_status

    def get_user_picks_for_week(
        self, user: UserModel, year: int, week_number: int, league_id: int
    ) -> UserPicksDto:
        # Resolve the league-season these picks belong to
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )

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
            (PickModel.user == user.id)
            & (PickModel.league_season == league_season.id)
            & (PickModel.game << games)
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
