from src.components.pick.kickoff import has_started
from src.components.pick.pick_models import (
    AdminSubmitPicksRequestDto,
    PickRequest,
    PickStatus,
    SubmitPicksRequestDto,
    PickDto,
    PickOverrideDto,
    PickOverrideSlotDto,
    UserPicksDto,
    TeamDto,
)
from src.security.security_models import DecodedToken
from src.components.league.league_exceptions import (
    NotALeagueMemberException,
)
from src.components.league.league_service import LeagueService
from src.components.user.user_exceptions import UserNotFoundException
from src.components.results.results_models import MatchupDto

# `admin:<username>`, the same actor form week.updated_by carries. Shared
# rather than re-spelled here: the value is only useful if every override in
# the application writes it identically.
from src.components.week.week_service import admin_actor
from src.config.base_service import BaseService
from src.models.db_models import (
    GameModel,
    PickModel,
    PickOverrideModel,
    UserModel,
    WeekModel,
    SeasonModel,
    GameResultModel,
    LeagueSeasonModel,
    TeamModel,
)
from peewee import DoesNotExist
from src.components.pick.pick_exceptions import (
    InvalidGameIDException,
    InvalidSlateException,
    InvalidTeamIDException,
    InvalidSeasonException,
    InvalidWeekException,
    LockedPickException,
    LockOverrideNotAcknowledgedException,
    InvalidGameWeekException,
    OverrideNotFoundException,
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
        actor: str | None = None,
    ) -> None:
        """
        Creates new picks or updates existing picks for the user in the database with the given status.

        Expects to be called inside a transaction -- see PickService._write_week,
        which opens one around the delete as well, so a failure here cannot
        leave the week short of the picks that were cleared for it.

        :param picks_data: The picks submitted by the user.
        :param user: The user submitting the picks.
        :param status: The status to apply to the picks.
        :param league_season: The league-season these picks belong to.
        :param actor: Who to record as the author, for an override. None leaves
            the "system" default that every player submission has always
            written.
        """
        # Not `instance.save()`, which is where this used to go: BaseModel.save
        # overwrites updated_by with "system" unconditionally, so an override
        # routed through it would record no author at all. The classmethod
        # update() honours an explicit value and defaults to the same "system"
        # when none is given.
        update_stamp = {"updated_by": actor} if actor else {}
        create_stamp = {"created_by": actor, "updated_by": actor} if actor else {}

        for pick in picks_data.picks:
            existing_pick = PickModel.get_or_none(
                (PickModel.user_id == user.id)
                & (PickModel.league_season_id == league_season.id)
                & (PickModel.game_id == pick.game_id)
            )

            if existing_pick:
                PickModel.update(
                    team=pick.team_id,
                    spread_value=pick.spread_value,
                    confidence=pick.confidence,
                    status=status,
                    **update_stamp,
                ).where(PickModel.id == existing_pick.id).execute()
                self.logger.info(
                    f"Pick updated for game ID {pick.game_id} " f"and user ID {user.id}"
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
                    **create_stamp,
                )
                self.logger.info(
                    f"Pick created for game ID {pick.game_id} " f"and user ID {user.id}"
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

    def _validate_slate(self, picks_data: SubmitPicksRequestDto) -> None:
        """
        That the week being written is well formed: five distinct games at five
        distinct confidences.

        Only the override path runs this. The player path deliberately accepts
        a partial slate -- picks can be saved and returned to -- and its UI
        always submits an ordered five, so it cannot produce either fault. An
        admin editing picks one field at a time can produce both, and neither
        is caught anywhere else: `pick` is unique on (user, league_season,
        game) but has no constraint on confidence, and scoring is a plain sum,
        so a duplicated 5 would quietly inflate a total rather than fail.
        """
        game_ids = [pick.game_id for pick in picks_data.picks]
        duplicates = {game_id for game_id in game_ids if game_ids.count(game_id) > 1}
        if duplicates:
            raise InvalidSlateException(
                f"A slate cannot pick the same game twice; game(s) "
                f"{', '.join(str(game_id) for game_id in sorted(duplicates))} appear more than once."
            )

        confidences = sorted(int(pick.confidence) for pick in picks_data.picks)
        if confidences != [1, 2, 3, 4, 5]:
            raise InvalidSlateException(
                f"A slate must use each confidence from 1 to 5 exactly once; got "
                f"{', '.join(str(value) for value in confidences)}."
            )

    def _started_games_disturbed(
        self,
        picks_data: SubmitPicksRequestDto,
        started_game_ids: list[int],
        existing_by_game: dict,
        submitted_game_ids: list[int],
    ) -> list[int]:
        """
        Which started games this submission would change or drop.

        Advisory rather than authoritative: it lets the override path refuse
        before it writes, and tells the audit row whether kickoff was actually
        bypassed. The guards below remain the enforcement, so under-reporting
        here fails safe -- the write is still refused, just with a less
        specific message.
        """
        started = set(started_game_ids)
        disturbed = set()

        for pick in picks_data.picks:
            if pick.game_id not in started:
                continue
            current = existing_by_game.get(pick.game_id)
            if current is None or not self._is_same_pick(current, pick):
                disturbed.add(pick.game_id)

        # Dropping a started pick by leaving it out is the same act as changing
        # it, and reads identically in the audit row.
        for game_id in existing_by_game:
            if game_id in started and game_id not in submitted_game_ids:
                disturbed.add(game_id)

        return sorted(disturbed)

    def _reject_removals_of_started_picks(
        self,
        existing_picks: list[PickModel],
        started_game_ids: list[int],
        submitted_game_ids: list[int],
    ) -> None:
        """
        Refuse to drop a pick whose game has started, however the submission
        arrived -- omitting it would otherwise delete it.
        """
        for pick in existing_picks:
            if pick.game_id not in submitted_game_ids and (
                pick.game_id in started_game_ids or pick.status == PickStatus.Locked
            ):
                raise LockedPickException(
                    f"Pick for game ID {pick.game_id} is locked and cannot be removed."
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
        A player writing their own week.

        :param pick_data: The picks submitted by the user.
        :param user: The user submitting the picks.
        :return: The status of the submitted picks.
        :raises LockedPickException: If a user attempts to change or remove a
            pick whose game has started.
        :raises InvalidGameWeekException: If any pick's game does not belong to the specified year and week.
        """
        self.logger.info(
            f"attempting to submit picks {pick_data} for user {user.username} "
            f"in league {league_id}"
        )

        # Authorize from the token. The year lives in the request body, so this
        # cannot be a path-parameter dependency like the other league routes.
        if not (
            token.is_admin or token.is_member(league_id=league_id, year=pick_data.year)
        ):
            raise NotALeagueMemberException(
                username=user.username, league_id=league_id, year=pick_data.year
            )

        league_season = self.league_service.get_league_season(
            league_id=league_id, year=pick_data.year
        )

        return self._write_week(
            pick_data=pick_data,
            user=user,
            league_season=league_season,
            actor=None,
            override_locked=False,
        )

    async def override_picks(
        self,
        pick_data: AdminSubmitPicksRequestDto,
        username: str,
        league_id: int,
        token: DecodedToken,
    ) -> PickStatus:
        """
        An admin or commissioner writing somebody else's week.

        The route has already established that the caller commissions this
        league or is a global admin -- see LeaguePermission.commissioner, which
        admits both. What is left to establish here is the *target*: `pick` is
        RESTRICTed against `league_member` at the database, so writing a row for
        somebody who never played that season would surface as an IntegrityError
        and a 500. It is a 403 instead, which is what it actually is.

        Note that a commissioner may reach their own picks this way. That is the
        access model you get by letting the person who fields the complaints fix
        them; the pick_override row is what makes a self-edit legible afterwards
        rather than preventing it.
        """
        target = self._get_user(username)
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=pick_data.year
        )

        if not self.league_service.get_membership(
            user=target, league_season=league_season
        ):
            raise NotALeagueMemberException(
                username=target.username, league_id=league_id, year=pick_data.year
            )

        self._validate_slate(pick_data)

        actor = admin_actor(token.sub)
        self.logger.warning(
            f"{actor} is overriding {target.username}'s week {pick_data.week} "
            f"picks in league {league_id} ({pick_data.year}), "
            f"override_locked={pick_data.override_locked}: {pick_data.reason}"
        )

        return self._write_week(
            pick_data=pick_data,
            user=target,
            league_season=league_season,
            actor=actor,
            override_locked=pick_data.override_locked,
            reason=pick_data.reason,
        )

    def _write_week(
        self,
        pick_data: SubmitPicksRequestDto,
        user: UserModel,
        league_season: LeagueSeasonModel,
        *,
        actor: str | None,
        override_locked: bool,
        reason: str | None = None,
    ) -> PickStatus:
        """
        The one place a week's picks are written, for a player's own submission
        and for an override alike.

        Only two things differ between them, and both are parameters: who is
        stamped on the rows, and whether kickoff is allowed to refuse the write.
        Everything else -- that the games exist, that the chosen teams play in
        them, that they fall in the week being claimed -- holds for both. One
        function rather than two, so the half that is easy to forget cannot
        drift away from the half that is exercised every Sunday.
        """
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

        disturbed = self._started_games_disturbed(
            picks_data=pick_data,
            started_game_ids=started_game_ids,
            existing_by_game=existing_by_game,
            submitted_game_ids=submitted_game_ids,
        )

        if not override_locked:
            # An override that has not said it means to break a lock is told
            # how to say so, rather than being refused outright the way a
            # player is. Checked before the guards below so the admin gets the
            # actionable message instead of a bare "this pick is locked".
            if actor is not None and disturbed:
                raise LockOverrideNotAcknowledgedException(game_ids=disturbed)

            # A started game's pick is frozen. The client resubmits it unchanged
            # as part of the week's full slate, so an identical value is allowed
            # through; anything else is an attempt to pick after kickoff.
            self._reject_changes_to_started_games(
                picks_data=pick_data,
                started_game_ids=started_game_ids,
                existing_by_game=existing_by_game,
            )
            self._reject_removals_of_started_picks(
                existing_picks=existing_picks,
                started_game_ids=started_game_ids,
                submitted_game_ids=submitted_game_ids,
            )
        elif disturbed:
            self.logger.warning(
                f"{actor} is bypassing kickoff on game(s) "
                f"{', '.join(str(game_id) for game_id in disturbed)}"
            )

        # Read the slate before anything touches it, for the audit row. From
        # the rows already in memory, so it costs no extra query and cannot
        # race the delete below.
        before_state = self._serialize_slate(existing_picks)

        # Started games are preserved through a normal submission whether or
        # not it mentions them; an override may drop them like any other, so
        # only what it actually submitted survives.
        preserved_game_ids = (
            submitted_game_ids
            if override_locked
            else submitted_game_ids + started_game_ids
        )

        # The delete and the write are one unit. They were not before, so an
        # upsert that failed after the delete succeeded left the player short
        # of the picks it had just cleared to make room for.
        with PickModel._meta.database.atomic():
            # Delete picks from this week that were left out of the submission.
            PickModel.delete().where(
                (PickModel.user_id == user.id)
                & (PickModel.league_season_id == league_season.id)
                & (PickModel.game_id.not_in(preserved_game_ids))
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
                actor=actor,
            )

            if actor is not None:
                PickOverrideModel.create(
                    league_season=league_season,
                    user=user,
                    week_number=pick_data.week,
                    actor=actor,
                    reason=reason or "",
                    before_state=before_state,
                    after_state=self._serialize_slate(
                        pick_data.picks, status=new_status
                    ),
                    locks_bypassed=bool(override_locked and disturbed),
                    created_by=actor,
                    updated_by=actor,
                )

        return new_status

    @staticmethod
    def _serialize_slate(picks, status: str | None = None) -> list[dict]:
        """
        A week's picks as an audit row stores them, in confidence order.

        Takes stored PickModels and submitted PickRequests alike -- they carry
        the same field names -- so the before and after halves of a record are
        built by one function and are directly comparable. Denormalised: ids
        and numbers only, nothing resolved through a foreign key, so the row
        still reads correctly once the spread or the team behind it has moved.
        """
        return [
            {
                "gameId": pick.game_id,
                "teamId": pick.team_id,
                "spreadValue": round(float(pick.spread_value), 2),
                "confidence": int(pick.confidence),
                "status": str(status or pick.status),
            }
            for pick in sorted(picks, key=lambda item: -int(item.confidence))
        ]

    def _resolve_slates(
        self, records: list[PickOverrideModel]
    ) -> dict[int, list[PickOverrideSlotDto]]:
        """
        Turn every stored slate in `records` into display rows, naming the
        teams.

        One team query for the whole page rather than one per slot. A log of a
        season's overrides is a few hundred slots pointing at thirty-two teams,
        so resolving them row by row is the same handful of teams fetched over
        and over.

        A team that no longer exists leaves its name null rather than dropping
        the row -- the pick still happened, and a slot missing from a recorded
        slate would misrepresent what was picked.
        """
        team_ids = {
            slot.get("teamId")
            for record in records
            for state in (record.before_state or [], record.after_state or [])
            for slot in state
            if slot.get("teamId") is not None
        }

        teams = (
            {
                team.id: team
                for team in TeamModel.select().where(TeamModel.id << list(team_ids))
            }
            if team_ids
            else {}
        )

        def to_slots(state: list[dict]) -> list[PickOverrideSlotDto]:
            return [
                PickOverrideSlotDto(
                    game_id=slot.get("gameId"),
                    team_id=slot.get("teamId"),
                    team_name=getattr(teams.get(slot.get("teamId")), "name", None),
                    team_abbreviation=getattr(
                        teams.get(slot.get("teamId")), "abbreviation", None
                    ),
                    spread_value=float(slot.get("spreadValue", 0)),
                    confidence=int(slot.get("confidence", 0)),
                    status=slot.get("status"),
                )
                for slot in state
            ]

        return {
            record.id: (
                to_slots(record.before_state or []),
                to_slots(record.after_state or []),
            )
            for record in records
        }

    def _to_override_dtos(
        self, records: list[PickOverrideModel]
    ) -> list[PickOverrideDto]:
        resolved = self._resolve_slates(records)
        return [
            PickOverrideDto(
                id=record.id,
                username=record.user.username,
                actor=record.actor,
                week=record.week_number,
                reason=record.reason,
                locks_bypassed=record.locks_bypassed,
                before=resolved[record.id][0],
                after=resolved[record.id][1],
                created_at=record.created_at,
            )
            for record in records
        ]

    def list_overrides(self, league_id: int, year: int) -> list[PickOverrideDto]:
        """Every override recorded against a league-season, newest first."""
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )

        records = list(
            # UserModel in the select, not just the join: the username is read
            # for every row, and without it peewee re-fetches the user once per
            # record.
            PickOverrideModel.select(PickOverrideModel, UserModel)
            .join(UserModel, on=(PickOverrideModel.user == UserModel.id))
            .where(PickOverrideModel.league_season == league_season.id)
            .order_by(PickOverrideModel.created_at.desc())
        )

        return self._to_override_dtos(records)

    def get_override_history(
        self, league_id: int, year: int, username: str
    ) -> list[PickOverrideDto]:
        """Every override recorded against one player's season, newest first."""
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )
        target = self._get_user(username)

        records = list(
            PickOverrideModel.select(PickOverrideModel, UserModel)
            .join(UserModel, on=(PickOverrideModel.user == UserModel.id))
            .where(
                (PickOverrideModel.league_season == league_season.id)
                & (PickOverrideModel.user == target.id)
            )
            .order_by(PickOverrideModel.created_at.desc())
        )

        return self._to_override_dtos(records)

    async def revert_override(
        self,
        override_id: int,
        league_id: int,
        year: int,
        token: DecodedToken,
        reason: str | None = None,
    ) -> PickStatus:
        """
        Put a week back the way an override found it.

        Writes a new record rather than removing the old one, so the log keeps
        reading forwards: what was done, then that it was undone, by whom and
        when. Nothing is ever deleted from it, which is the only property that
        makes it worth consulting.

        Restoring is deliberately not held to the five-pick rule an override is.
        The state being restored is whatever was really there, and a player who
        had saved three picks and not finished is a state this has to be able
        to reproduce exactly -- including the state of having had none at all.
        """
        league_season = self.league_service.get_league_season(
            league_id=league_id, year=year
        )

        record = PickOverrideModel.get_or_none(
            (PickOverrideModel.id == override_id)
            # Scoped to the league-season in the path, not just the id. Without
            # it, an id from another league would be reverted by anyone who
            # commissions this one.
            & (PickOverrideModel.league_season == league_season.id)
        )
        if record is None:
            raise OverrideNotFoundException(
                override_id=override_id, league_id=league_id, year=year
            )

        target = record.user
        actor = admin_actor(token.sub)
        restore_reason = reason or f"Reverted override #{override_id}"
        before = record.before_state or []

        self.logger.warning(
            f"{actor} is reverting override #{override_id} "
            f"({target.username}, week {record.week_number}): {restore_reason}"
        )

        if not before:
            # The week had nothing in it. Restoring that means removing what the
            # override put there, which is not a slate write at all -- there is
            # nothing to write.
            return self._clear_week(
                user=target,
                league_season=league_season,
                year=year,
                week=record.week_number,
                actor=actor,
                reason=restore_reason,
            )

        return self._write_week(
            pick_data=SubmitPicksRequestDto(
                year=year,
                week=record.week_number,
                picks=[
                    PickRequest(
                        game_id=slot["gameId"],
                        team_id=slot["teamId"],
                        spread_value=slot["spreadValue"],
                        confidence=slot["confidence"],
                    )
                    for slot in before
                ],
            ),
            user=target,
            league_season=league_season,
            actor=actor,
            # A revert almost always reaches games that have been played --
            # that is usually why it is being reverted.
            override_locked=True,
            reason=restore_reason,
        )

    def _clear_week(
        self,
        user: UserModel,
        league_season: LeagueSeasonModel,
        year: int,
        week: int,
        actor: str,
        reason: str,
    ) -> PickStatus:
        """
        Remove every pick a player has in one week, and record it.

        Only reachable by reverting an override that found the week empty. A
        player cannot get here: their own submission requires at least one pick,
        so "delete my whole week" is not something the pick routes offer.

        Separate from _write_week rather than an empty slate through it. That
        path would mostly work -- peewee turns `not_in([])` into `1 = 1`, so its
        delete would clear the week -- but it would leave the week marked SAVED
        with nothing in it, and "delete everything" would be resting on an empty
        NOT IN collapsing to a tautology, which is not a thing to depend on
        quietly.
        """
        existing = list(
            PickModel.select()
            .join(GameModel, on=(PickModel.game == GameModel.id))
            .join(WeekModel, on=(GameModel.week == WeekModel.id))
            .join(SeasonModel, on=(GameModel.season == SeasonModel.id))
            .where(
                (PickModel.user_id == user.id)
                & (PickModel.league_season_id == league_season.id)
                & (WeekModel.week_number == week)
                & (SeasonModel.year == year)
            )
        )

        before_state = self._serialize_slate(existing)

        with PickModel._meta.database.atomic():
            PickModel.delete().where(
                (PickModel.user_id == user.id)
                & (PickModel.league_season_id == league_season.id)
                & (
                    PickModel.game.in_(
                        GameModel.select(GameModel.id)
                        .join(WeekModel)
                        .join(SeasonModel)
                        .where(
                            (WeekModel.week_number == week) & (SeasonModel.year == year)
                        )
                    )
                )
            ).execute()

            PickOverrideModel.create(
                league_season=league_season,
                user=user,
                week_number=week,
                actor=actor,
                reason=reason,
                before_state=before_state,
                after_state=[],
                # Anything already played that this removed counts as bypassing
                # a lock, the same as changing it would.
                locks_bypassed=any(has_started(pick.game) for pick in existing),
                created_by=actor,
                updated_by=actor,
            )

        return PickStatus.New

    def _get_user(self, username: str) -> UserModel:
        """A typo'd username is a 404, not an uncaught DoesNotExist -> 500."""
        try:
            return UserModel.get(UserModel.username == username)
        except DoesNotExist:
            self.logger.error(f"User '{username}' not found")
            raise UserNotFoundException(username=username)

    def get_player_picks_for_week(
        self, username: str, year: int, week_number: int, league_id: int
    ) -> UserPicksDto:
        """
        Somebody else's week, for a commissioner about to change it.

        A thin wrapper rather than a widened get_user_picks_for_week: the
        reader of that function should not have to work out which callers can
        pass an arbitrary user. Here the answer is in the name, and the route
        above it is commissioner-gated.
        """
        return self.get_user_picks_for_week(
            self._get_user(username),
            year,
            week_number,
            league_id=league_id,
        )

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
