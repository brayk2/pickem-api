from typing import Literal

from pydantic import Field

from src.models.base_models import BaseDto


class ClientEvent(BaseDto):
    """
    Something the browser saw go wrong. Unauthenticated -- it has to work when
    auth is what's broken -- so every field is bounded.
    """

    type: Literal["api_error", "api_slow", "js_error", "render_error"]
    # API call facts; `status` is absent when the browser never got a response
    # (timeout, CORS-blocked gateway error, offline).
    method: str | None = Field(default=None, max_length=10)
    route: str | None = Field(default=None, max_length=300)
    status: int | None = None
    error_code: str | None = Field(default=None, max_length=50)
    duration_ms: int | None = Field(default=None, ge=0)
    request_id: str | None = Field(default=None, max_length=64)
    # Page and error facts.
    page: str | None = Field(default=None, max_length=300)
    message: str | None = Field(default=None, max_length=500)
    online: bool | None = None
    occurred_at: int | None = None


class ClientEventBatch(BaseDto):
    events: list[ClientEvent] = Field(max_length=25)
    app_version: str | None = Field(default=None, max_length=30)
    session_id: str | None = Field(default=None, max_length=64)
