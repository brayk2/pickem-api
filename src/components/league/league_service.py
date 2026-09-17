from peewee import DoesNotExist, IntegrityError

from src.components.auth.auth_models import LeagueClaim
from src.components.league.league_exceptions import (
    DuplicateLeagueException,
    DuplicateLeagueMemberException,
    LeagueNotFoundException,
    LeagueSeasonNotFoundException,
    NotALeagueMemberException,
)
from src.components.league.league_models import (
    LeagueDto,
    LeagueMemberDto,
    LeagueRole,
    LeagueRosterDto,
    LeagueSeasonDto,
)
from src.components.user.user_exceptions import UserNotFoundException
from src.config.base_service import BaseService
from src.models.db_models import (
    LeagueMemberModel,
    LeagueModel,
    LeagueSeasonModel,
    SeasonModel,
    UserModel,
)
from src.util.injection import dependency


@dependency
class LeagueService(BaseService):
    """
    Resolves leagues, their per-year instances, and their rosters.

    A league is durable across years; a league_season is one league's run in one
    year. Membership hangs off the league_season, so a player who sits out a year
    simply has no row for it and their history stays intact.

    This service does not authorize requests. Permission checks read the `leagues`
    claim on the token (see get_league_claims and LeaguePermission) so that no
    database round trip is needed per request.
    """

    def get_league(self, league_id: int) -> LeagueModel:
        try:
            return LeagueModel.get_by_id(league_id)
        except DoesNotExist:
            self.logger.error(f"League {league_id} not found")
            raise LeagueNotFoundException(league_id=league_id)

    def get_league_season(self, league_id: int, year: int) -> LeagueSeasonModel:
        """
        Resolves the league-season a request is scoped to. This is the unit every
        pick, standing, and result is filtered by.
        """
        try:
            return (
                LeagueSeasonModel.select()
                .join(SeasonModel, on=(LeagueSeasonModel.season == SeasonModel.id))
                .where(
                    (LeagueSeasonModel.league == league_id) & (SeasonModel.year == year)
                )
                .get()
            )
        except DoesNotExist:
            self.logger.error(f"League {league_id} has no season for year {year}")
            # Distinguish "no such league" from "league did not run that year".
            self.get_league(league_id=league_id)
            raise LeagueSeasonNotFoundException(league_id=league_id, year=year)

    def _get_user(self, username: str) -> UserModel:
        """A typo'd username is a 404, not an uncaught DoesNotExist -> 500."""
        try:
            return UserModel.get(UserModel.username == username)
        except DoesNotExist:
            self.logger.error(f"User '{username}' not found")
            raise UserNotFoundException(username=username)

    def get_membership(
        self, user: UserModel, league_season: LeagueSeasonModel
    ) -> LeagueMemberModel | None:
        return LeagueMemberModel.get_or_none(
            (LeagueMemberModel.user == user.id)
            & (LeagueMemberModel.league_season == league_season.id)
        )

    def list_leagues(self, token=None) -> list[LeagueDto]:
        """
        Leagues the caller belongs to. Admins see all of them.

        Filtering here rather than returning 403s keeps the client simple: it
        asks for "my leagues" and gets exactly that.
        """
        leagues = [
            LeagueDto.model_validate(league)
            for league in LeagueModel.select().order_by(LeagueModel.name)
        ]

        if token is None or token.is_admin:
            return leagues

        return [league for league in leagues if token.is_in_league(league.id)]

    def create_league(self, name: str, description: str | None = None) -> LeagueDto:
        self.logger.info(f"Creating league: {name}")
        try:
            league = LeagueModel.create(name=name, description=description)
        except IntegrityError:
            raise DuplicateLeagueException(name=name)
        return LeagueDto.model_validate(league)

    def list_league_seasons(self, league_id: int) -> list[LeagueSeasonDto]:
        self.get_league(league_id=league_id)
        return [
            LeagueSeasonDto(
                id=ls.id,
                league_id=ls.league_id,
                year=ls.season.year,
                settings=ls.settings or {},
            )
            for ls in (
                LeagueSeasonModel.select()
                .join(SeasonModel, on=(LeagueSeasonModel.season == SeasonModel.id))
                .where(LeagueSeasonModel.league == league_id)
                .order_by(SeasonModel.year)
            )
        ]

    def start_season(self, league_id: int, year: int) -> LeagueSeasonDto:
        """Opens a league for a new year. The roster starts empty by design."""
        league = self.get_league(league_id=league_id)
        try:
            season = SeasonModel.get(SeasonModel.year == year)
        except DoesNotExist:
            raise LeagueSeasonNotFoundException(league_id=league_id, year=year)

        league_season, created = LeagueSeasonModel.get_or_create(
            league=league, season=season
        )
        if created:
            self.logger.info(f"Opened league {league_id} for {year}")

        return LeagueSeasonDto(
            id=league_season.id,
            league_id=league_season.league_id,
            year=year,
            settings=league_season.settings or {},
        )

    def get_roster(self, league_id: int, year: int) -> LeagueRosterDto:
        league_season = self.get_league_season(league_id=league_id, year=year)
        return LeagueRosterDto(
            league_id=league_id,
            year=year,
            members=self.list_members(league_season=league_season),
        )

    def list_members(self, league_season: LeagueSeasonModel) -> list[LeagueMemberDto]:
        return [
            LeagueMemberDto(
                user_id=member.user.id,
                username=member.user.username,
                first_name=member.user.first_name,
                last_name=member.user.last_name,
                role=member.role,
            )
            for member in (
                LeagueMemberModel.select(LeagueMemberModel, UserModel)
                .join(UserModel, on=(LeagueMemberModel.user == UserModel.id))
                .where(LeagueMemberModel.league_season == league_season.id)
                .order_by(UserModel.username)
            )
        ]

    def list_members_by_season(
        self, league_season_ids: list[int]
    ) -> dict[int, list[LeagueMemberDto]]:
        """
        Rosters for several league-seasons at once, keyed by league-season id.

        The league history seeds each season's standings from that season's
        roster. Asking for them one at a time is a query per year, which grows
        for as long as the league keeps running.
        """
        if not league_season_ids:
            return {}

        rosters: dict[int, list[LeagueMemberDto]] = {
            season_id: [] for season_id in league_season_ids
        }

        for member in (
            LeagueMemberModel.select(LeagueMemberModel, UserModel)
            .join(UserModel, on=(LeagueMemberModel.user == UserModel.id))
            .where(LeagueMemberModel.league_season.in_(list(league_season_ids)))
            .order_by(UserModel.username)
        ):
            rosters[member.league_season_id].append(
                LeagueMemberDto(
                    user_id=member.user.id,
                    username=member.user.username,
                    first_name=member.user.first_name,
                    last_name=member.user.last_name,
                    role=member.role,
                )
            )

        return rosters

    def add_member(
        self,
        league_id: int,
        year: int,
        username: str,
        role: LeagueRole = LeagueRole.Member,
    ) -> LeagueMemberDto:
        """
        Adds a player to one year's roster.

        The new member's token does not yet carry this league, so their access
        begins on their next token refresh.
        """
        league_season = self.get_league_season(league_id=league_id, year=year)
        user = self._get_user(username)

        try:
            LeagueMemberModel.create(
                league_season=league_season, user=user, role=str(role)
            )
        except IntegrityError:
            raise DuplicateLeagueMemberException(username=username, year=year)

        self.logger.info(f"Added {username} to league {league_id} for {year}")
        return LeagueMemberDto(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            role=role,
        )

    def remove_member(self, league_id: int, year: int, username: str) -> None:
        """
        Removes a player from one year's roster. Their picks are protected by the
        RESTRICT foreign key, so this fails rather than destroying history if they
        already played.

        Their existing access token still carries this league until it expires.
        """
        league_season = self.get_league_season(league_id=league_id, year=year)
        user = self._get_user(username)

        membership = self.get_membership(user=user, league_season=league_season)
        if not membership:
            raise NotALeagueMemberException(
                username=username, league_id=league_id, year=year
            )

        membership.delete_instance()
        self.logger.info(f"Removed {username} from league {league_id} for {year}")

    def get_league_claims(self, user: UserModel) -> dict[str, LeagueClaim]:
        """
        Builds the `leagues` token claim in a single query.

        Called at login and refresh only. Permission checks then read the token
        rather than the database, so a roster change reaches the holder on their
        next refresh -- at most the access token lifetime.
        """
        claims: dict[str, LeagueClaim] = {}

        rows = (
            LeagueMemberModel.select(
                LeagueSeasonModel.league.alias("league_id"),
                SeasonModel.year.alias("year"),
                LeagueMemberModel.role.alias("role"),
            )
            .join(
                LeagueSeasonModel,
                on=(LeagueMemberModel.league_season == LeagueSeasonModel.id),
            )
            .join(SeasonModel, on=(LeagueSeasonModel.season == SeasonModel.id))
            .where(LeagueMemberModel.user == user.id)
            .dicts()
        )

        for row in rows:
            claim = claims.setdefault(str(row["league_id"]), LeagueClaim())
            claim.years.append(row["year"])
            if row["role"] == LeagueRole.Commissioner:
                claim.commissioner = True

        for claim in claims.values():
            claim.years.sort()

        self.logger.info(f"Built league claims for {user.username}: {claims}")
        return claims
