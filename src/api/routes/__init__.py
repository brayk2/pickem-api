from fastapi import APIRouter

from src.api.routes.admin_router import admin_router
from src.api.routes.game_router import game_router
from src.api.routes.league_router import league_router
from src.api.routes.player_router import player_router
from src.api.routes.spread_router import spread_router
from src.api.routes.team_router import team_router

api = APIRouter(prefix="/api")

api.include_router(admin_router)
api.include_router(spread_router)
api.include_router(game_router)
api.include_router(player_router)
api.include_router(league_router)
api.include_router(team_router)
