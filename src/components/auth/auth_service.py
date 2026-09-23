import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from src.components.auth.auth_models import (
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
)
from src.components.email.email_models import EmailMessage
from src.components.email.email_service import EmailService
from src.components.league.league_service import LeagueService
from src.components.roles.roles_service import RolesService
from src.components.user.user_service import UserService
from src.config.base_service import BaseService
from src.integrations.queue_service import QueueService
from src.models.db_models import UserModel
from src.security.oauth_service import OAuthService
from src.security.security_exceptions import IncorrectCredentialsException
from src.security.security_models import TokenResponse
from src.util.injection import dependency, inject
from src.models.db_models import PasswordResetTokensModel

PASSWORD_RESET_TTL_MINUTES = 30
PASSWORD_RESET_URL = "https://pickem-webapp.vercel.app/reset-password?token={token}"


@dependency
class AuthService(BaseService):
    """
    Issues and refreshes access tokens.

    Every token carries the holder's global roles and their per-league standing,
    so both are re-read from the database whenever a token is minted.
    """

    @inject
    def __init__(
        self,
        oauth_service: OAuthService,
        user_service: UserService,
        roles_service: RolesService,
        league_service: LeagueService,
        queue_service: QueueService,
    ):
        self.oauth_service = oauth_service
        self.user_service = user_service
        self.roles_service = roles_service
        self.league_service = league_service
        self.queue_service = queue_service

    def login(self, username: str, password: str) -> TokenResponse:
        # Validate user credentials
        user = self.user_service.get_user_by_username(username)
        if not user or not self.oauth_service.verify_password(
            password, user.password_hash
        ):
            raise IncorrectCredentialsException()

        return self._generate_tokens(user=user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        decoded_token = self.oauth_service.decode_token(refresh_token)

        # Re-read roles and league standing so a refresh picks up roster changes
        user = self.user_service.get_user_by_username(decoded_token.sub)
        return self._generate_tokens(user=user)

    def _generate_tokens(self, user: UserModel) -> TokenResponse:
        roles = self.roles_service.get_roles_for_user(user=user)
        leagues = self.league_service.get_league_claims(user=user)

        return self.oauth_service.generate_tokens(
            username=user.username, roles=roles, leagues=leagues
        )

    @staticmethod
    def _generate_password_reset_token():
        return secrets.token_urlsafe(32)

    def request_password_reset(self, password_reset_request: PasswordResetRequestBody):
        user = self.user_service.get_user_by_email(email=password_reset_request.email)
        if not user:
            self.logger.info(
                f"user with email={password_reset_request.email} does not exist"
            )
            return

        # handle token generation, hashing, and notifying
        token = self._generate_password_reset_token()
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=PASSWORD_RESET_TTL_MINUTES
        )

        password_reset_model = PasswordResetTokensModel.create(
            user=user,
            token_hash=hashed_token,
            expires_at=expires_at,
            used_at=None,
        )

        self.queue_service.send_email(
            EmailMessage(
                recipient=user.email,
                subject="PickEm - Password Reset Request",
                message_parts=EmailService.render_template(
                    "password_reset",
                    name=user.first_name or user.username,
                    reset_url=PASSWORD_RESET_URL.format(token=token),
                    expires_minutes=PASSWORD_RESET_TTL_MINUTES,
                ),
            )
        )

        return

    def confirm_password_reset(
        self, password_reset_confirm: PasswordResetConfirmBody
    ): ...


def do_hash(val):
    return hashlib.sha256(val.encode()).hexdigest()


def verify_token(submitted_token, stored_hash):
    computed = do_hash(submitted_token)
    return secrets.compare_digest(computed, stored_hash)
