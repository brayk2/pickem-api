from datetime import datetime, timedelta
from typing import List

import boto3
import pytz
from botocore.exceptions import ClientError
from jose import JWTError, jwt
from passlib.context import CryptContext
from src.components.auth.auth_models import DecodedToken, TokenResponse
from src.components.auth.auth_exceptions import InvalidTokenException
from src.config.base_service import BaseService
from src.config.settings import Settings
from src.util.injection import dependency
import os

settings = Settings()


def get_secret():
    # Create a Secrets Manager client
    client = boto3.client(service_name="secretsmanager")
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=settings.secret_path
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response["SecretString"]
    return secret


@dependency
class OAuthService(BaseService):
    """
    Service for handling OAuth-related operations including token creation,
    password hashing, and token decoding.
    """

    def __init__(
        self,
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
        self.secret_key = get_secret()
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifies a password against its hashed version.

        :param plain_password: The plain text password to verify.
        :param hashed_password: The hashed password to compare against.
        :return: True if the password matches, False otherwise.
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """
        Hashes a plain text password.

        :param password: The plain text password to hash.
        :return: The hashed password.
        """
        return self.pwd_context.hash(password)

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
        to_encode.update({"exp": expire.timestamp() * 1000})

        return (
            jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm),
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
            payload_dict = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
            return DecodedToken.from_dict(payload_dict)
        except JWTError:
            raise InvalidTokenException()

    def generate_tokens(self, username: str, roles: List[str]) -> TokenResponse:
        """
        Generates both an access token and a refresh token for the user.

        :param username: The username to encode in the tokens.
        :param roles: The roles associated with the user.
        :return: A Token object containing the access and refresh tokens.
        """
        payload = DecodedToken(sub=username, roles=roles)
        access_token, access_token_dict = self.create_access_token(payload)
        refresh_token, _ = self.create_refresh_token(payload)

        return TokenResponse(
            token_type="Bearer",
            access_token=access_token,
            refresh_token=refresh_token,
            expiration=access_token_dict.get("exp"),
        )
