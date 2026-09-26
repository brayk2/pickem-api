import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field

# A client-supplied id is echoed into logs and response headers, so only
# accept something that looks like an id.
_CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,64}$")


@dataclass
class RequestContext:
    """
    Per-request facts gathered for the request log line.

    Held in a ContextVar and mutated in place rather than re-set: FastAPI runs
    sync dependencies in a threadpool with a *copy* of the context, so a
    `set()` there would be lost, but mutations to this shared object are not.
    """

    request_id: str
    apigw_request_id: str | None = None
    lambda_request_id: str | None = None
    user: str | None = None
    db_ms: float = 0.0
    db_queries: int = 0
    db_connect_ms: float = 0.0
    extra: dict = field(default_factory=dict)


_current: ContextVar[RequestContext | None] = ContextVar(
    "request_context", default=None
)


def resolve_request_id(client_id: str | None, apigw_request_id: str | None) -> str:
    if client_id and _CLIENT_ID_PATTERN.match(client_id):
        return client_id
    return apigw_request_id or str(uuid.uuid4())


def start(ctx: RequestContext):
    return _current.set(ctx)


def reset(token) -> None:
    _current.reset(token)


def current() -> RequestContext | None:
    return _current.get()


def set_user(username: str | None) -> None:
    ctx = _current.get()
    if ctx is not None:
        ctx.user = username
