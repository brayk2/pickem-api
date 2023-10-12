# league router

from fastapi import APIRouter
from src.config.logger import get_logger
from src.models.dto.league_dtos import League, LeagueRequest
from src.services.league_service import LeagueService

logger = get_logger(__name__)
league_service = LeagueService()

league_router = APIRouter(prefix="/league", tags=["League"])


@league_router.get("/{id}", response_model=League)
def get_league(id: int):
    return league_service.get_league(id)


@league_router.post("", response_model=League)
def create_league(request: LeagueRequest):
    raise NotImplementedError("create league not implemented")


@league_router.put("/{id}", response_model=League)
def update_league(id: int, request: LeagueRequest):
    raise NotImplementedError("update league not implemented")


@league_router.delete("/{id}")
def delete_league(id: int):
    raise NotImplementedError("delete league not implemented")
