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

    class Meta:
        table_name = "week"
        indexes = (
            (("season", "week_number"), True),  # Unique index on season and week_number
        )


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
    start_date = DateField()  # New field for the start date of the game
    start_time = TimeField()  # New field for the start time of the game

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
                ("user", "game"),
                True,
            ),  # Ensure a user cannot submit more than one pick per game
        )


class ActionModel(BaseModel):
    name = CharField()
    type = CharField()
    arn = CharField

    class Meta:
        table_name = "action"
