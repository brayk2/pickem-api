from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware
from src.api.routes.ping_router import ping_router
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.components.admin.admin_router import admin_router
from src.api.routes.game_router import game_router
from src.components.pick.pick_router import picks_router
from src.api.routes.scrape_router import scrape_router
from src.api.routes.spread_router import spread_router
from src.api.routes.team_router import team_router
from src.components.auth.auth_router import auth_router
from src.components.results.results_router import results_router
from src.components.roles.roles_router import roles_router
from src.components.standings.standings_router import standings_router
from src.components.user.user_router import user_router
from src.components.season.season_router import season_router
from src.config.logger import Logger

app = FastAPI(title="PickEm Api", version="0.0.1", root_path="/")
logger = Logger()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.middleware("http")
async def exception_handling_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except StarletteHTTPException as exc:
        logger.exception(exc)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    except RequestValidationError as exc:
        logger.exception(exc)
        return JSONResponse(
            status_code=422, content={"detail": exc.errors(), "body": exc.body}
        )
    except Exception as exc:
        logger.exception(exc)
        return JSONResponse(
            status_code=500, content={"detail": "An unexpected error occurred."}
        )


api = APIRouter(prefix="/api")

# new component structure
api.include_router(auth_router)
api.include_router(season_router)
api.include_router(user_router)
api.include_router(roles_router)
api.include_router(results_router)
api.include_router(standings_router)

# old route structure
# api.include_router(auth_router)
# api.include_router(users_router)
api.include_router(picks_router)
api.include_router(admin_router)
api.include_router(spread_router)
api.include_router(game_router)
api.include_router(team_router)
api.include_router(scrape_router)

app.include_router(api)
app.include_router(ping_router)

handler = Mangum(app)
