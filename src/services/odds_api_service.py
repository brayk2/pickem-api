import datetime
import functools
from typing import TypeVar

import httpx
from pydantic import BaseModel, Field, TypeAdapter

from src.components.admin.admin_service import AdminService
from src.config.base_service import BaseService
from src.services.property_service import PropertyService
from src.util.injection import dependency, inject


def empty_list(v: any) -> any:
    if not v:
        return []
    return v


T = TypeVar("T", bound=BaseModel)


def validate_response(model: type[T | list[T]]):
    def wrapper(f):
        @functools.wraps(f)
        def inner(*args, **kwargs) -> T | list[T]:
            output = f(*args, **kwargs)
            if isinstance(output, list):
                return TypeAdapter(list[model.__args__[0]]).validate_python(output)
            return model.model_validate(output)

        return inner

    return wrapper


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
    last_updated: datetime.datetime | None = Field(default=None)
    scores: list[ScoreDto]


class OutcomeDto(BaseModel):
    name: str
    price: int | None = Field(default=None)
    point: float | None = Field(default=None)


class MarketDto(BaseModel):
    key: str
    last_update: datetime.datetime | None = Field(default=None)
    outcomes: list[OutcomeDto]


class BookmakerDto(BaseModel):
    key: str
    title: str
    last_update: datetime.datetime | None = Field(default=None)
    markets: list[MarketDto]


class OddsDto(GameDto):
    bookmakers: list[BookmakerDto]


@dependency
class OddsApiService(BaseService):
    @inject
    def __init__(self, admin_service: AdminService, property_service: PropertyService):
        self.base_url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
        self.admin_service = admin_service
        self.property_service = property_service

    @property
    def client(self) -> httpx.Client:
        return httpx.Client(
            timeout=60, base_url=self.base_url, headers={"accept": "*/*"}
        )

    def save_remaining(self, response: httpx.Response):
        try:
            self.admin_service.set_oddsapi_quota(
                quota={
                    "used": response.headers.get("x-requests-used"),
                    "remaining": response.headers.get("x-requests-remaining"),
                }
            )
        except Exception as e:
            self.logger.info(f"failed to save api quota : {e}")

    @validate_response(model=list[OddsDto])
    def fetch_odds(
        self, start_date: datetime.datetime, end_date: datetime.datetime
    ) -> list[OddsDto]:
        start_time = (
            datetime.datetime.combine(start_date, datetime.time()).isoformat() + "Z"
        )
        end_time = (
            datetime.datetime.combine(
                end_date + datetime.timedelta(days=1), datetime.time()
            ).isoformat()
            + "Z"
        )
        response = self.client.get(
            url="odds",
            params={
                "regions": "us",
                "markets": "spreads",
                "oddsFormat": "american",
                "apiKey": self.settings.odds_api_key,
                "commenceTimeFrom": start_time,
                "commenceTimeTo": end_time,
            },
        )
        self.save_remaining(response=response)
        response.raise_for_status()
        return response.json()

    @validate_response(model=list[ScoresDto])
    def fetch_scores(self) -> list[ScoresDto]:
        response = self.client.get(
            url="scores",
            params={
                "daysFrom": "1",
                "apiKey": self.settings.odds_api_key,
            },
        )
        self.save_remaining(response=response)
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    scores = OddsApiService().fetch_scores()
    print(scores)
