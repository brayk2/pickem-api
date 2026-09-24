import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from src.components.auth.auth_models import (
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
)
from src.components.email.email_models import EmailMessage
from src.components.user.user_exceptions import BadRequestException
from src.components.email.email_service import EmailService
from src.components.league.league_service import LeagueService
from src.components.roles.roles_service import RolesService
from src.components.user.user_service import UserService
from src.config.base_service import BaseService
from src.integrations.queue_service import QueueService
from src.models.db_models import PasswordResetTokensModel, UserModel
from src.security.oauth_service import OAuthService
from src.security.security_exceptions import IncorrectCredentialsException
from src.security.security_models import TokenResponse
from src.util.injection import dependency, inject

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

    @staticmethod
    def _hash_password_reset_token(token: str) -> str:
        # Only the hash is stored, so a leaked table can't be replayed. The
        # token is 256 random bits, so an unsalted sha256 is enough to look it
        # up by.
        return hashlib.sha256(token.encode()).hexdigest()

    def request_password_reset(self, password_reset_request: PasswordResetRequestBody):
        user = self.user_service.get_user_by_email(email=password_reset_request.email)
        if not user:
            self.logger.info(
                f"user with email={password_reset_request.email} does not exist"
            )
            return

        # handle token generation, hashing, and notifying
        token = self._generate_password_reset_token()
        hashed_token = self._hash_password_reset_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=PASSWORD_RESET_TTL_MINUTES
        )

        PasswordResetTokensModel.create(
            user=user,
            token_hash=hashed_token,
            expires_at=expires_at,
            used_at=None,
        )

        # A failure here is logged rather than raised: a 500 only for known
        # addresses would tell the caller which emails have accounts, which is
        # what the unconditional 202 is there to hide.
        try:
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
        except Exception:
            self.logger.exception(
                f"failed to queue password reset email for user {user.username}"
            )

    def confirm_password_reset(
        self, password_reset_confirm: PasswordResetConfirmBody
    ) -> dict:
        token_hash = self._hash_password_reset_token(password_reset_confirm.token)
        now = datetime.now(timezone.utc)

        with PasswordResetTokensModel._meta.database.atomic():
            # Spend the token and learn whose it is in one statement, so two
            # submits of the same link can't both get through.
            spent = list(
                PasswordResetTokensModel.update(used_at=now)
                .where(
                    (PasswordResetTokensModel.token_hash == token_hash)
                    & PasswordResetTokensModel.used_at.is_null()
                    & (PasswordResetTokensModel.expires_at > now)
                )
                .returning(PasswordResetTokensModel.user)
                .tuples()
                .execute()
            )
            if not spent:
                raise BadRequestException(
                    "This password reset link is invalid or has expired."
                )
            user_id = spent[0][0]

            UserModel.update(
                password_hash=self.oauth_service.get_password_hash(
                    password=password_reset_confirm.new_password
                )
            ).where(UserModel.id == user_id).execute()

            # Any other links still sitting in the inbox are now stale.
            PasswordResetTokensModel.update(used_at=now).where(
                (PasswordResetTokensModel.user == user_id)
                & PasswordResetTokensModel.used_at.is_null()
            ).execute()

        self.logger.info(f"password reset for user id {user_id}")
        return {"message": "Your password has been reset."}
