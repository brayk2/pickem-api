from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config import request_context
from src.security.security_models import DecodedToken
from src.security.security_exceptions import (
    InvalidTokenException,
    InsufficientRoleException,
)
from src.security.oauth_service import OAuthService


class PermissionChecker:
    """
    Global permission gates.

    Only `admin` is a global role. Everything else is scoped to a league and is
    checked against `league_member.role` at the point where the league is known
    -- see LeaguePermission and LeagueService.require_membership /
    require_commissioner. League roles are deliberately absent from the token:
    they vary per league, so putting them in the JWT would require reissuing it
    every time someone joins a league.
    """

    _admin: str = "admin"

    @staticmethod
    def _get_current_user(
        token: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
        oauth_service: OAuthService = Depends(OAuthService.create),
    ) -> DecodedToken:
        try:
            payload = oauth_service.decode_token(token.credentials)
        except Exception:
            raise InvalidTokenException
        request_context.set_user(payload.sub)
        return payload

    @classmethod
    def authenticated(
        cls, current_user: DecodedToken = Depends(_get_current_user)
    ) -> DecodedToken:
        """Any valid token. Use for routes that are not league-specific."""
        return current_user

    @classmethod
    def admin(
        cls, current_user: DecodedToken = Depends(_get_current_user)
    ) -> DecodedToken:
        if cls._admin not in current_user.roles:
            raise InsufficientRoleException(role=cls._admin)
        return current_user
