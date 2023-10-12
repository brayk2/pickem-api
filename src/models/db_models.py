from peewee import (
    Model,
    DateTimeField,
    CharField,
    BigAutoField,
    FloatField,
    IntegerField,
    ForeignKeyField,
    BooleanField,
)
from datetime import datetime

from playhouse.postgres_ext import JSONField

from src.config.db_connection import get_database


class BaseModel(Model):
    class Meta:
        database = get_database()

    system_user = "system"
    id: int = BigAutoField()
    created_at: datetime = DateTimeField(default=datetime.now())
    created_by: str = CharField(default=system_user)
    updated_at: datetime = DateTimeField(default=datetime.now())
    updated_by: str = CharField(default=system_user)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        self.updated_by = self.system_user
        return super().save(*args, **kwargs)

    def update(self, *args, **kwargs):
        self.updated_at = datetime.now()
        self.updated_by = self.system_user
        return super().update(*args, **kwargs)


class PlayerModel(BaseModel):
    username: str = CharField()
    email: str = CharField()

    class Meta:
        table_name = "player"


class SeasonModel(BaseModel):
    year: str = CharField()

    class Meta:
        table_name = "season"


class TeamModel(BaseModel):
    name: str = CharField(unique=True)
    reference: str = CharField(null=True)
    thumbnail: str = CharField(null=True)

    @property
    def mascot(self):
        _, _, mascot = self.name.rpartition(" ")
        return mascot

    @property
    def location(self):
        location, _, _ = self.name.rpartition(" ")
        return location

    class Meta:
        table_name = "team"


class GameModel(BaseModel):
    season: SeasonModel = ForeignKeyField(
        backref="games", column_name="season_id", field="id", model=SeasonModel
    )
    home_team: TeamModel = ForeignKeyField(
        model=TeamModel,
        column_name="home_team",
        field="name",
    )
    away_team: TeamModel = ForeignKeyField(
        model=TeamModel,
        column_name="away_team",
        field="name",
    )
    reference: str = CharField(null=True)
    start_time: datetime = DateTimeField(null=True)
    oddsapi_id: str = CharField(unique=True, null=True)
    week: str = CharField(null=True)

    class Meta:
        table_name = "game"


class SpreadModel(BaseModel):
    game: GameModel = ForeignKeyField(
        backref="spreads", column_name="game_id", field="id", model=GameModel
    )
    bookmaker: str = CharField()
    home_point_spread: float = FloatField()
    away_point_spread: float = FloatField()
    home_spread_price: int = IntegerField()
    away_spread_price: int = IntegerField()

    class Meta:
        table_name = "spread"


class LeagueModel(BaseModel):
    name: str = CharField()

    class Meta:
        table_name = "league"


class LeaguePlayerRelationModel(BaseModel):
    league: LeagueModel = ForeignKeyField(
        column_name="league_id", field="id", model=LeagueModel
    )
    player: PlayerModel = ForeignKeyField(
        column_name="player_id", field="id", model=PlayerModel
    )

    class Meta:
        table_name = "league_player_relation"


class PropertyModel(BaseModel):
    key: str = CharField()
    value: dict = JSONField()
    category: str = CharField()

    class Meta:
        table_name = "property"


class ResultsModel(BaseModel):
    completed: bool = BooleanField(null=True, default=False)
    home_score: int = IntegerField(default=0)
    away_score: int = IntegerField(default=0)
    game: GameModel = ForeignKeyField(
        backref="results",
        model=GameModel,
    )

    class Meta:
        table_name = "results"
