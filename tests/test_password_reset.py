import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from peewee import SqliteDatabase

from src.app import app
from src.components.auth.auth_models import (
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
)
from src.components.auth.auth_service import AuthService
from src.components.user.user_exceptions import BadRequestException
from src.models.db_models import PasswordResetTokensModel, UserModel

MODELS = [UserModel, PasswordResetTokensModel]


class _FakeOAuth:
    def get_password_hash(self, password):
        return f"hashed:{password}"


class _FakeUsers:
    def get_user_by_email(self, email):
        return UserModel.get_or_none(UserModel.email == email)


class _FakeQueue:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def send_email(self, email):
        if self.fail:
            raise RuntimeError("queue down")
        self.sent.append(email)


@pytest.fixture
def db():
    test_db = SqliteDatabase(":memory:")
    with test_db.bind_ctx(MODELS):
        test_db.create_tables(MODELS)
        yield test_db


@pytest.fixture
def user(db):
    return UserModel.create(
        username="sam",
        email="sam@example.com",
        first_name="Sam",
        last_name="Smith",
        password_hash="hashed:old",
    )


def _service(queue=None):
    return AuthService(
        oauth_service=_FakeOAuth(),
        user_service=_FakeUsers(),
        roles_service=None,
        league_service=None,
        queue_service=queue or _FakeQueue(),
    )


def _issue_token(user, token="tok", expires_in=timedelta(minutes=30), used=False):
    now = datetime.now(timezone.utc)
    PasswordResetTokensModel.create(
        user=user,
        token_hash=AuthService._hash_password_reset_token(token),
        expires_at=now + expires_in,
        used_at=now if used else None,
    )
    return token


def _confirm(service, token, password="brand-new-pw"):
    return service.confirm_password_reset(
        PasswordResetConfirmBody(token=token, new_password=password)
    )


def test_request_stores_only_the_hash_and_emails_the_raw_token(user):
    queue = _FakeQueue()
    _service(queue).request_password_reset(
        PasswordResetRequestBody(email="sam@example.com")
    )

    row = PasswordResetTokensModel.get()
    [email] = queue.sent
    body = "".join(part.content for part in email.message_parts)
    token = re.search(r"reset-password\?token=([\w-]+)", body).group(1)
    assert email.recipient == "sam@example.com"
    assert row.token_hash == AuthService._hash_password_reset_token(token)
    assert token not in row.token_hash


def test_request_for_unknown_email_does_nothing(db):
    queue = _FakeQueue()
    _service(queue).request_password_reset(
        PasswordResetRequestBody(email="nobody@example.com")
    )
    assert queue.sent == []
    assert PasswordResetTokensModel.select().count() == 0


def test_request_swallows_queue_failure(user):
    # Raising would answer differently for known addresses.
    _service(_FakeQueue(fail=True)).request_password_reset(
        PasswordResetRequestBody(email="sam@example.com")
    )


def test_confirm_sets_the_password_and_spends_the_token(user):
    token = _issue_token(user)

    assert _confirm(_service(), token) == {"message": "Your password has been reset."}

    assert UserModel.get_by_id(user.id).password_hash == "hashed:brand-new-pw"
    assert PasswordResetTokensModel.get().used_at is not None


def test_confirm_twice_fails_the_second_time(user):
    token = _issue_token(user)
    _confirm(_service(), token)

    with pytest.raises(BadRequestException):
        _confirm(_service(), token, password="another-pw")
    assert UserModel.get_by_id(user.id).password_hash == "hashed:brand-new-pw"


@pytest.mark.parametrize(
    "issue",
    [
        dict(expires_in=timedelta(minutes=-1)),
        dict(used=True),
    ],
    ids=["expired", "already-used"],
)
def test_confirm_rejects_dead_tokens(user, issue):
    token = _issue_token(user, **issue)

    with pytest.raises(BadRequestException):
        _confirm(_service(), token)
    assert UserModel.get_by_id(user.id).password_hash == "hashed:old"


def test_confirm_rejects_unknown_token(user):
    with pytest.raises(BadRequestException):
        _confirm(_service(), "never-issued")


def test_confirm_burns_the_users_other_links(user):
    first = _issue_token(user, token="first")
    second = _issue_token(user, token="second")

    _confirm(_service(), second)

    with pytest.raises(BadRequestException):
        _confirm(_service(), first)


class _FakeAuth:
    def __init__(self, error=None):
        self.error = error
        self.confirmed = None

    def confirm_password_reset(self, password_reset_confirm):
        if self.error:
            raise self.error
        self.confirmed = password_reset_confirm
        return {"message": "Your password has been reset."}


def _post_confirm(fake, body):
    app.dependency_overrides[AuthService.create] = lambda: fake
    try:
        return TestClient(app).post("/auth/token/password-reset/confirm", json=body)
    finally:
        app.dependency_overrides.clear()


def test_confirm_route_accepts_the_webapps_camel_case_body():
    fake = _FakeAuth()
    response = _post_confirm(fake, {"token": "abc", "newPassword": "longenough"})

    assert response.status_code == 200
    assert response.json() == {"message": "Your password has been reset."}
    assert fake.confirmed.new_password == "longenough"


def test_confirm_route_answers_400_for_a_dead_token():
    fake = _FakeAuth(error=BadRequestException("expired"))
    response = _post_confirm(fake, {"token": "abc", "newPassword": "longenough"})

    assert response.status_code == 400
    assert response.json() == {"detail": "expired"}


def test_confirm_route_rejects_short_passwords():
    response = _post_confirm(_FakeAuth(), {"token": "abc", "newPassword": "short"})
    assert response.status_code == 422
