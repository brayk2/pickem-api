from datetime import datetime
from peewee import (
    Model,
    BigAutoField,
    DateTimeField,
    CharField,
    IntegerField,
    ForeignKeyField,
    BooleanField,
    DecimalField,
    DateField,
    TimeField,
    TextField,
    Check,
)
from playhouse.postgres_ext import JSONField
from playhouse.shortcuts import model_to_dict

from src.config.db_connection import get_database

database = get_database()


class BaseModel(Model):
    class Meta:
        database = database

    system_user = "system"
    id: BigAutoField = BigAutoField()
    created_at: datetime = DateTimeField(default=datetime.now)
    created_by: str = CharField(default=system_user)
    updated_at: datetime = DateTimeField(default=datetime.now)
    updated_by: str = CharField(default=system_user)

    def to_dict(self, exclude_none: bool = False):
        as_dict = model_to_dict(self)
        if exclude_none:
            as_dict = {key: val for key, val in as_dict.items() if val}

        return as_dict

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        self.updated_by = self.system_user
        return super().save(*args, **kwargs)

    def _update_instance(self, *args, **kwargs):
        """Internal method for updating instance data."""
        self.updated_at = datetime.now()
        self.updated_by = self.system_user
        return super().update(*args, **kwargs)

    def update_instance(self, **query):
        """Custom update method for updating this model instance."""
        query.update({"updated_at": datetime.now(), "updated_by": self.system_user})
        return self._update_instance().where(self._pk_expr()).execute()

    @classmethod
    def update(cls, **update_data):
        """Overrides the default update method."""
        if "updated_at" not in update_data:
            update_data["updated_at"] = datetime.now()
        if "updated_by" not in update_data:
            update_data["updated_by"] = cls.system_user
        return super().update(**update_data)


class UserModel(BaseModel):
    username = CharField(unique=True)
    email = CharField(unique=True)
    first_name: str = CharField()
    last_name: str = CharField()
    password_hash = CharField()

    @property
    def groups(self) -> list[str]:
        return [
            group.name
            for group in GroupModel.select()
            .join(UserGroupModel)
            .where(UserGroupModel.user == self)
        ]

    class Meta:
        table_name = "user"


class GroupModel(BaseModel):
    name = CharField(unique=True)
    description = CharField(null=True)

    class Meta:
        table_name = "group"


class UserGroupModel(BaseModel):
    user = ForeignKeyField(UserModel, backref="user_groups", on_delete="CASCADE")
    group = ForeignKeyField(GroupModel, backref="user_groups", on_delete="CASCADE")

    class Meta:
        table_name = "user_group"
        indexes = ((("user", "group"), True),)  # Unique index on user and group


class SeasonModel(BaseModel):
    year = IntegerField()

    class Meta:
        table_name = "season"


class WeekModel(BaseModel):
    season = ForeignKeyField(SeasonModel, backref="weeks", on_delete="CASCADE")
    week_number = IntegerField()
    start_date = DateField(null=True)
    end_date = DateField(null=True)
    # Set once every game in the week has a final score, and overridable by an
    # admin. Gates the end-of-week statistics: a half-finished week would show
    # a "most missed pick" that the Monday night game is about to overturn.
    completed = BooleanField(default=False)

    class Meta:
        table_name = "week"
        indexes = (
            (("season", "week_number"), True),  # Unique index on season and week_number
        )


class LeagueModel(BaseModel):
    name = CharField(unique=True)
    description = CharField(null=True)

    class Meta:
        table_name = "league"


class LeagueSeasonModel(BaseModel):
    """A single league's run in a single season. Rules that vary year to year
    (scoring, tiebreakers, buy-in) belong in `settings`, not on LeagueModel."""

    league = ForeignKeyField(LeagueModel, backref="league_seasons", on_delete="CASCADE")
    season = ForeignKeyField(SeasonModel, backref="league_seasons", on_delete="CASCADE")
    settings = JSONField(default=dict)

    class Meta:
        table_name = "league_season"
        indexes = ((("league", "season"), True),)


class LeagueMemberModel(BaseModel):
    """The roster for one league-season. A player who sits out a year simply has
    no row here for it; the UserModel is never deleted, so history is preserved."""

    league_season = ForeignKeyField(
        LeagueSeasonModel, backref="members", on_delete="CASCADE"
    )
    user = ForeignKeyField(UserModel, backref="league_memberships", on_delete="CASCADE")
    role = CharField(
        default="MEMBER",
        constraints=[Check("role IN ('MEMBER', 'COMMISSIONER')")],
    )

    class Meta:
        table_name = "league_member"
        indexes = ((("league_season", "user"), True),)


class TeamModel(BaseModel):
    name = CharField()
    city = CharField()
    abbreviation = CharField()
    thumbnail = CharField(null=True)
    primary_color = CharField(null=True, max_length=7)
    secondary_color = CharField(null=True, max_length=7)

    class Meta:
        table_name = "team"

    @property
    def full_name(self):
        return f"{self.city} {self.name}"


class GameModel(BaseModel):
    season = ForeignKeyField(SeasonModel, backref="games", on_delete="CASCADE")
    week = ForeignKeyField(WeekModel, backref="games", on_delete="CASCADE")
    home_team = ForeignKeyField(TeamModel, backref="home_games", on_delete="CASCADE")
    away_team = ForeignKeyField(TeamModel, backref="away_games", on_delete="CASCADE")
    # Nullable, and legitimately so: the NFL flex-schedules, so a game has no
    # kickoff until the league sets one. kickoff() returns None for those and
    # has_started() refuses to lock a pick on a time nobody knows. Declared
    # non-null here while the column was nullable, which is the wrong way round
    # -- the database was right.
    start_date = DateField(null=True)
    start_time = TimeField(null=True)

    class Meta:
        table_name = "game"


class SpreadModel(BaseModel):
    game = ForeignKeyField(GameModel, backref="spreads", on_delete="CASCADE")
    team = ForeignKeyField(
        TeamModel, backref="spreads", on_delete="CASCADE"
    )  # Indicates which team the spread applies to
    bookmaker = CharField()  # New field for the bookmaker name
    spread_value = DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        table_name = "spread"
        indexes = (
            (
                ("game", "team", "bookmaker"),
                True,
            ),  # Unique constraint on game, team, and bookmaker combination
        )


class GameResultModel(BaseModel):
    game = ForeignKeyField(
        GameModel, backref="result", on_delete="CASCADE", unique=True
    )
    home_score = IntegerField()
    away_score = IntegerField()

    class Meta:
        table_name = "game_result"


class TeamResultModel(BaseModel):
    game = ForeignKeyField(GameModel, backref="team_results", on_delete="CASCADE")
    season = ForeignKeyField(SeasonModel, backref="team_results", on_delete="CASCADE")
    team = ForeignKeyField(TeamModel, backref="team_results", on_delete="CASCADE")
    home = BooleanField()
    win = BooleanField()
    cover = BooleanField()
    points_scored = IntegerField()
    points_allowed = IntegerField()

    class Meta:
        table_name = "team_result"
        indexes = ((("game", "team"), True),)  # Unique index on game and team


class PropertyModel(BaseModel):
    key: str = CharField()
    value: dict = JSONField()
    category: str = CharField()

    class Meta:
        table_name = "property"


class PickModel(BaseModel):
    user = ForeignKeyField(UserModel, backref="pick", on_delete="CASCADE")
    league_season = ForeignKeyField(
        LeagueSeasonModel, backref="picks", on_delete="CASCADE"
    )
    game = ForeignKeyField(GameModel, backref="pick", on_delete="CASCADE")
    team = ForeignKeyField(TeamModel, backref="pick", on_delete="CASCADE")
    confidence = IntegerField(
        constraints=[Check("confidence >= 0 AND confidence <= 5")]
    )
    spread_value = DecimalField(max_digits=5, decimal_places=2)
    status = CharField(default="NEW")  # Added status field

    class Meta:
        table_name = "pick"
        indexes = (
            (
                ("user", "league_season", "game"),
                True,
            ),  # One pick per game per league; the same user may play several leagues
        )


class PickOverrideModel(BaseModel):
    """
    An admin or commissioner having changed some other player's picks.

    Append-only. `pick.updated_by` records who wrote a row last, which the next
    write overwrites -- so it cannot say what a slate looked like before it was
    touched, and that is the only question anyone asks about an override.
    """

    league_season = ForeignKeyField(
        LeagueSeasonModel, backref="pick_overrides", on_delete="CASCADE"
    )
    # The target: whose picks these are, not who changed them. The actor is a
    # string, in the same `admin:<username>` form week.updated_by uses, so the
    # record survives the account that caused it.
    user = ForeignKeyField(UserModel, backref="pick_overrides", on_delete="CASCADE")
    week_number = IntegerField()
    actor = CharField()
    reason = TextField()
    # Denormalised slates, so they stay readable after the game, team or spread
    # they refer to has changed underneath them.
    before_state = JSONField(default=list)
    after_state = JSONField(default=list)
    locks_bypassed = BooleanField(default=False)

    class Meta:
        table_name = "pick_override"


class ActionModel(BaseModel):
    name = CharField()
    type = CharField()
    arn = CharField

    class Meta:
        table_name = "action"


class PasswordResetTokensModel(BaseModel):
    user = ForeignKeyField(
        UserModel, backref="password_reset_tokens", on_delete="CASCADE"
    )
    token_hash = CharField(max_length=64, unique=True)
    expires_at = DateTimeField()
    used_at = DateTimeField(null=True)

    class Meta:
        table_name = "password_reset_tokens"
