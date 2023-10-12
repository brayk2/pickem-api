import datetime
import functools
from typing import Optional, TypeVar, Annotated

import httpx
from pydantic import BaseModel, Field, TypeAdapter, BeforeValidator

from src.config.base_service import BaseService
from src.services.property_service import PropertyService
from src.util.injection import dependency, inject


def empty_list(v: any) -> any:
    if not v:
        return []
    return v


L = TypeVar("L")
List = Annotated[list[L], BeforeValidator(empty_list)]


class GameDto(BaseModel):
    game_id: str = Field(alias="id")
    start_time: datetime.datetime = Field(alias="commence_time")
    home_team: str
    away_team: str


class ScoreDto(BaseModel):
    name: str
    score: int


class ScoresDto(GameDto):
    completed: bool
    last_updated: Optional[datetime.datetime] = Field(default=None)
    scores: List[ScoreDto]


class OutcomeDto(BaseModel):
    name: str
    price: Optional[int] = Field(default=None)
    point: Optional[float] = Field(default=None)


class MarketDto(BaseModel):
    key: str
    last_update: Optional[datetime.datetime] = Field(default=None)
    outcomes: List[OutcomeDto]


class BookmakerDto(BaseModel):
    key: str
    title: str
    last_update: Optional[datetime.datetime] = Field(default=None)
    markets: List[MarketDto]


class OddsDto(GameDto):
    bookmakers: List[BookmakerDto]


T = TypeVar("T", bound=BaseModel)


def validate_response(model: type[T | list[T]]):
    def wrapper(f):
        @functools.wraps(f)
        def inner(*args, **kwargs) -> T | list[T]:
            output = f(*args, **kwargs)
            if model.__origin__ is list:
                return TypeAdapter(model).validate_python(output)
            return model.model_validate(output)

        return inner

    return wrapper


@dependency
class OddsApiService(BaseService):
    @inject
    def __init__(self, property_service: PropertyService):
        self.property_service = property_service
        self.base_url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"

    @property
    def client(self):
        return httpx.Client(
            timeout=60, base_url=self.base_url, headers={"accept": "*/*"}
        )

    def save_remaining(self, response: httpx.Response):
        self.property_service.set_oddsapi_quota(
            quota={
                "used": response.headers.get("x-requests-used"),
                "remaining": response.headers.get("x-requests-remaining"),
            }
        )

    @validate_response(model=list[OddsDto])
    def fetch_odds(self):
        response = self.client.get(
            url="odds",
            params={
                "regions": "us",
                "markets": "spreads",
                "oddsFormat": "american",
                "apiKey": self.settings.odds_api_key,
            },
        )
        self.save_remaining(response=response)
        response.raise_for_status()
        return response.json()

    @validate_response(model=list[ScoresDto])
    def fetch_scores(self):
        response = self.client.get(
            url="scores",
            params={
                "daysFrom": "3",
                "apiKey": self.settings.odds_api_key,
            },
        )
        self.save_remaining(response=response)
        response.raise_for_status()
        return response.json()
