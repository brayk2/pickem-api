from datetime import datetime, timedelta
from typing import List
import pytz
from jose import ExpiredSignatureError, JWTError, jwt
from src.security.security_models import (
    DecodedToken,
    LeagueClaim,
    TokenResponse,
)
from src.security.security_exceptions import InvalidTokenException
from src.config.base_service import BaseService
from src.config.settings import Settings
from src.security.password_manager import PasswordManager
from src.integrations.secret_service import DEFAULT_MAX_AGE_S, SecretService
from src.util.injection import dependency, inject


@dependency
class OAuthService(BaseService):
    """
    Service for handling OAuth-related operations including token creation,
    password hashing, and token decoding.
    """

    @inject
    def __init__(
        self,
        secret_service: SecretService,
        settings: Settings,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,  # Short-lived access tokens
        refresh_token_expire_days: int = 7,  # Long-lived refresh tokens
    ):
        """
        Initializes the OAuthService.

        :param algorithm: The JWT algorithm to use for encoding and decoding.
        :param access_token_expire_minutes: The expiration time for access tokens.
        :param refresh_token_expire_days: The expiration time for refresh tokens.
        """
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.secret_service = secret_service
        self.settings = settings

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifies a password against its hashed version.

        :param plain_password: The plain text password to verify.
        :param hashed_password: The hashed password to compare against.
        :return: True if the password matches, False otherwise.
        """
        return PasswordManager.verify_password(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """
        Hashes a plain text password.

        :param password: The plain text password to hash.
        :return: The hashed password.
        """
        return PasswordManager.hash_password(password)

    def create_access_token(self, payload: DecodedToken) -> tuple[str, dict]:
        """
        Creates a new short-lived access token.

        :param payload: The payload to encode in the token.
        :return: The encoded JWT access token as a string.
        """
        return self._create_token(payload, self.access_token_expire_minutes)

    def create_refresh_token(self, payload: DecodedToken) -> tuple[str, dict]:
        """
        Creates a new long-lived refresh token.

        :param payload: The payload to encode in the token.
        :return: The encoded JWT refresh token as a string.
        """
        return self._create_token(payload, self.refresh_token_expire_days * 1440)

    def _create_token(
        self, payload: DecodedToken, expires_minutes: int
    ) -> tuple[str, dict]:
        """
        Helper method to create a JWT token with an expiration time.

        :param payload: The payload to encode in the token.
        :param expires_minutes: The expiration time in minutes.
        :return: The encoded JWT token as a string.
        """
        to_encode = payload.to_dict()
        expire = datetime.now(tz=pytz.UTC) + timedelta(minutes=expires_minutes)
        self.logger.info(f"expire timestamp = {expire.timestamp()}")
        # RFC 7519: `exp` is seconds since the epoch. Writing milliseconds here
        # made every token validate roughly 56,000 years into the future, so
        # tokens never expired. Clients that want milliseconds get them from
        # TokenResponse.expiration instead.
        to_encode.update({"exp": expire.timestamp()})

        return (
            jwt.encode(
                to_encode,
                # Always sign with the current key: a token signed with a
                # cached pre-rotation key would fail everywhere else.
                self.secret_service.get_secret(
                    secret_path=self.settings.secret_path, max_age_s=0
                ),
                algorithm=self.algorithm,
            ),
            to_encode,
        )

    def decode_token(self, token: str) -> DecodedToken:
        """
        Decodes a JWT token and validates it.

        :param token: The encoded JWT token to decode.
        :return: The decoded payload as a DecodedToken object.
        :raises InvalidTokenException: If the token is invalid or decoding fails.
        """
        try:
            payload_dict = self._decode(token, max_age_s=DEFAULT_MAX_AGE_S)
        except ExpiredSignatureError:
            raise InvalidTokenException()
        except JWTError:
            # The cached key may predate a rotation; check once more against
            # the current one before calling the token bad.
            try:
                payload_dict = self._decode(token, max_age_s=0)
            except JWTError:
                raise InvalidTokenException()
        return DecodedToken.from_dict(payload_dict)

    def _decode(self, token: str, max_age_s: float) -> dict:
        return jwt.decode(
            token,
            self.secret_service.get_secret(
                secret_path=self.settings.secret_path, max_age_s=max_age_s
            ),
            algorithms=[self.algorithm],
        )

    def generate_tokens(
        self,
        username: str,
        roles: List[str],
        leagues: dict[str, LeagueClaim] | None = None,
    ) -> TokenResponse:
        """
        Generates both an access token and a refresh token for the user.

        :param username: The username to encode in the tokens.
        :param roles: The global roles associated with the user.
        :param leagues: Per-league standing, so permission checks need no
            database round trip. See LeagueService.get_league_claims.
        :return: A Token object containing the access and refresh tokens.
        """
        payload = DecodedToken(sub=username, roles=roles, leagues=leagues or {})
        access_token, access_token_dict = self.create_access_token(payload)
        refresh_token, _ = self.create_refresh_token(payload)

        return TokenResponse(
            token_type="Bearer",
            access_token=access_token,
            refresh_token=refresh_token,
            # Milliseconds, unchanged, so existing clients doing `new Date(exp)`
            # keep working. The token's own `exp` claim stays in seconds.
            expiration=access_token_dict["exp"] * 1000,
        )
