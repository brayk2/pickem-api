from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.components.auth.auth_models import DecodedToken
from src.components.auth.auth_exceptions import (
    InvalidTokenException,
    InsufficientRoleException,
)
from src.services.oauth_service import OAuthService


class PermissionChecker:
    _player: str = "player"
    _admin: str = "admin"
    _commissioner: str = "commissioner"

    @staticmethod
    def _get_current_user(
        token: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
        oauth_service: OAuthService = Depends(OAuthService.create),
    ) -> DecodedToken:
        try:
            payload = oauth_service.decode_token(token.credentials)
            return payload
        except Exception:
            raise InvalidTokenException

    @classmethod
    def player(
        cls, current_user: DecodedToken = Depends(_get_current_user)
    ) -> DecodedToken:
        if cls._player not in current_user.roles:
            raise InsufficientRoleException(role=cls._player)
        return current_user

    @classmethod
    def admin(
        cls, current_user: DecodedToken = Depends(_get_current_user)
    ) -> DecodedToken:
        if cls._admin not in current_user.roles:
            raise InsufficientRoleException(role=cls._admin)
        return current_user

    @classmethod
    def commissioner(
        cls,
        current_user: DecodedToken = Depends(_get_current_user),
    ) -> DecodedToken:
        if cls._admin in current_user.roles:
            return current_user

        if cls._commissioner not in current_user.roles:
            raise InsufficientRoleException(role="commissioner")
        return current_user
