from src.components.league.league_service import LeagueService
from src.components.roles.roles_service import RolesService
from src.components.user.user_service import UserService
from src.config.base_service import BaseService
from src.models.db_models import UserModel
from src.security.oauth_service import OAuthService
from src.security.security_exceptions import IncorrectCredentialsException
from src.security.security_models import TokenResponse
from src.util.injection import dependency, inject


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
    ):
        self.oauth_service = oauth_service
        self.user_service = user_service
        self.roles_service = roles_service
        self.league_service = league_service

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
