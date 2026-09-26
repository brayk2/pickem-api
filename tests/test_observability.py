import json
import logging

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from jose import jwt
from peewee import OperationalError

from src.app import app
from src.config import request_context
from src.config.db_connection import LambdaPostgresqlDatabase
from src.config.logger import JsonFormatter
from src.security.oauth_service import OAuthService
from src.security.security_exceptions import InvalidTokenException

_boom = APIRouter()


@_boom.get("/__test/boom")
async def boom():
    raise RuntimeError("password=hunter2 leaked in a message")


app.include_router(_boom)
client = TestClient(app, raise_server_exceptions=False)


def test_every_response_carries_a_request_id():
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.headers["x-request-id"]


def test_a_well_formed_client_request_id_is_kept():
    response = client.get("/ping", headers={"X-Request-ID": "abc12345-def"})
    assert response.headers["x-request-id"] == "abc12345-def"


def test_a_malformed_client_request_id_is_replaced():
    response = client.get("/ping", headers={"X-Request-ID": "<script>"})
    assert response.headers["x-request-id"] != "<script>"


def test_unexpected_errors_hide_internals_but_return_the_request_id():
    response = client.get("/__test/boom")
    assert response.status_code == 500
    body = response.json()
    assert "hunter2" not in json.dumps(body)
    assert body["requestId"] == response.headers["x-request-id"]


def test_client_events_are_accepted():
    response = client.post(
        "/telemetry/client-events",
        json={
            "events": [
                {
                    "type": "api_error",
                    "method": "GET",
                    "route": "/standings",
                    "errorCode": "ERR_NETWORK",
                    "durationMs": 29001,
                }
            ],
            "appVersion": "1.0.14",
        },
    )
    assert response.status_code == 204


def test_client_event_batches_are_bounded():
    events = [{"type": "js_error", "message": "x"}] * 26
    response = client.post("/telemetry/client-events", json={"events": events})
    assert response.status_code == 422


def test_json_formatter_emits_fields_and_request_id():
    token = request_context.start(request_context.RequestContext(request_id="rid-1"))
    try:
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "hi", None, None)
        record.fields = {"route": "/x"}
        doc = json.loads(JsonFormatter().format(record))
    finally:
        request_context.reset(token)
    assert doc["message"] == "hi"
    assert doc["request_id"] == "rid-1"
    assert doc["route"] == "/x"


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        if self.conn.dead:
            raise OperationalError("SSL connection has been closed unexpectedly")


class _FakeConn:
    def __init__(self, dead):
        self.dead = dead
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        self.closed = True


def _db_with(conn, idle_s, usable=True):
    db = LambdaPostgresqlDatabase("x")
    db._state.set_connection(conn)
    db._last_used = -idle_s  # time.monotonic() is always well past this
    db.is_connection_usable = lambda: usable
    return db


def test_an_idle_dead_connection_is_discarded():
    conn = _FakeConn(dead=True)
    db = _db_with(conn, idle_s=10_000)
    db.discard_if_dead()
    assert db.is_closed()
    assert conn.closed


def test_an_idle_live_connection_is_kept():
    db = _db_with(_FakeConn(dead=False), idle_s=10_000)
    db.discard_if_dead()
    assert not db.is_closed()


def test_a_connection_stuck_in_a_failed_transaction_is_discarded():
    db = _db_with(_FakeConn(dead=False), idle_s=0, usable=False)
    db.discard_if_dead()
    assert db.is_closed()


class _RotatingSecrets:
    """Serves a stale key from 'cache' and the current key on a fresh fetch."""

    def __init__(self, cached, current):
        self.cached, self.current = cached, current

    def get_secret(self, secret_path, max_age_s=300):
        return self.current if max_age_s == 0 else self.cached


class _Settings:
    secret_path = "oauth"


def _token(key):
    return jwt.encode(
        {"sub": "sam", "roles": [], "exp": 9_999_999_999}, key, algorithm="HS256"
    )


def test_a_token_signed_after_rotation_validates_against_a_stale_cache():
    service = OAuthService(
        secret_service=_RotatingSecrets(cached="old", current="new"),
        settings=_Settings(),
    )
    assert service.decode_token(_token("new")).sub == "sam"


def test_a_token_with_an_unknown_key_is_still_rejected():
    service = OAuthService(
        secret_service=_RotatingSecrets(cached="old", current="new"),
        settings=_Settings(),
    )
    with pytest.raises(InvalidTokenException):
        service.decode_token(_token("forged"))
