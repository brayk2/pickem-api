import logging
import time

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from peewee import InterfaceError, OperationalError
from starlette.middleware.cors import CORSMiddleware
from src.components.health.health_router import health_router
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.components.admin.admin_router import admin_router
from src.components.game.game_router import game_router
from src.components.league.league_router import league_router
from src.components.pick.pick_router import picks_router
from src.components.scrape.scrape_router import scrape_router
from src.components.spread.spread_router import spread_router
from src.components.team.team_router import team_router
from src.components.auth.auth_router import auth_router
from src.components.results.results_router import results_router
from src.components.roles.roles_router import roles_router
from src.components.standings.standings_router import standings_router
from src.components.user.user_router import user_router
from src.components.season.season_router import season_router
from src.components.user.users_router import users_router
from src.components.telemetry.telemetry_router import telemetry_router
from src.config import request_context
from src.config.logger import Logger
from src.models.db_models import database

app = FastAPI(title="PickEm Api", version="0.0.1", root_path="/api")
logger = Logger()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    expose_headers=["X-Request-ID"],
)


_cold_start = True


def _route_template(request: Request) -> str:
    # The matched route's template ("/results/{league_id}/{year}/...") groups
    # requests usefully in log queries; the raw path would not.
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


@app.middleware("http")
async def exception_handling_middleware(request: Request, call_next):
    global _cold_start
    cold_start, _cold_start = _cold_start, False

    event = request.scope.get("aws.event") or {}
    lambda_context = request.scope.get("aws.context")
    apigw_request_id = (event.get("requestContext") or {}).get("requestId")
    ctx = request_context.RequestContext(
        request_id=request_context.resolve_request_id(
            request.headers.get("x-request-id"), apigw_request_id
        ),
        apigw_request_id=apigw_request_id,
        lambda_request_id=getattr(lambda_context, "aws_request_id", None),
    )
    token = request_context.start(ctx)
    started = time.perf_counter()
    status = 500

    try:
        # No eager connect: the first query connects, so routes that never
        # touch the database (ping, telemetry) never pay for it.
        database.discard_if_dead()

        response = await call_next(request)
        status = response.status_code
    except StarletteHTTPException as exc:
        logger.exception(exc)
        status = exc.status_code
        response = JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail}
        )
    except RequestValidationError as exc:
        logger.exception(exc)
        status = 422
        response = JSONResponse(
            status_code=422, content={"detail": exc.errors(), "body": exc.body}
        )
    except Exception as exc:
        logger.exception(exc)
        if isinstance(exc, (OperationalError, InterfaceError)):
            # The connection may be half-dead; don't hand it to the next request.
            database.discard(f"{type(exc).__name__} during request")
        # The exception text can carry SQL or internals -- it stays in the log,
        # and the request id lets a user report point straight at it.
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected error occurred",
                "requestId": ctx.request_id,
            },
        )
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        _log_request(request, ctx, status, duration_ms, cold_start)
        request_context.reset(token)

    response.headers["X-Request-ID"] = ctx.request_id
    return response


def _log_request(request, ctx, status, duration_ms, cold_start):
    fields = {
        "type": "request",
        "method": request.method,
        "route": _route_template(request),
        "path": request.url.path,
        "status": status,
        "duration_ms": round(duration_ms, 1),
        "db_ms": round(ctx.db_ms, 1),
        "db_queries": ctx.db_queries,
        "db_connect_ms": round(ctx.db_connect_ms, 1),
        "cold_start": cold_start,
        "user": ctx.user,
        "apigw_request_id": ctx.apigw_request_id,
        "lambda_request_id": ctx.lambda_request_id,
    }
    # Service-level only: a Route dimension would be a separately billed
    # metric per route. Per-route numbers come from Logs Insights instead.
    metrics = {
        "Requests": (1, "Count"),
        "ServerErrors": (1 if status >= 500 else 0, "Count"),
        "ClientErrors": (1 if 400 <= status < 500 else 0, "Count"),
        "Latency": (round(duration_ms, 1), "Milliseconds"),
        "DbTime": (round(ctx.db_ms, 1), "Milliseconds"),
        "ColdStarts": (1 if cold_start else 0, "Count"),
    }
    level = logging.ERROR if status >= 500 else logging.INFO
    logger.log(level, "request completed", extra={"fields": fields, "metrics": metrics})


# api = APIRouter(prefix="/api")

# new component structure
app.include_router(auth_router)
app.include_router(season_router)
app.include_router(user_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(results_router)
app.include_router(standings_router)
app.include_router(league_router)

# old route structure
# api.include_router(auth_router)
# api.include_router(users_router)
app.include_router(picks_router)
app.include_router(admin_router)
app.include_router(spread_router)
app.include_router(game_router)
app.include_router(team_router)
app.include_router(scrape_router)

# ping router
app.include_router(health_router)
app.include_router(telemetry_router)

handler = Mangum(app, api_gateway_base_path="/api")
