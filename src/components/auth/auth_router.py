from fastapi import APIRouter, Depends
from src.components.auth.auth_models import (
    TokenResponse,
    LoginRequest,
    TokenRefreshRequest,
)
from src.components.auth.auth_exceptions import IncorrectCredentialsException
from src.components.roles.roles_service import RolesService
from src.services.oauth_service import OAuthService
from src.components.user.user_service import UserService

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: LoginRequest,
    oauth_service: OAuthService = Depends(OAuthService.create),
    user_service: UserService = Depends(UserService.create),
    roles_service: RolesService = Depends(RolesService.create),
):
    # Validate user credentials
    user = user_service.get_user_by_username(form_data.username)
    if not user or not oauth_service.verify_password(
        form_data.password, user.password_hash
    ):
        raise IncorrectCredentialsException()

    # Get roles for user
    roles = roles_service.get_roles_for_user(user=user)

    # Use OAuthService to generate tokens, including fetching roles
    tokens = oauth_service.generate_tokens(username=user.username, roles=roles)

    return tokens


@auth_router.post("/token/refresh", response_model=TokenResponse)
async def refresh_access_token(
    token_refresh_request: TokenRefreshRequest,
    user_service: UserService = Depends(UserService.create),
    oauth_service: OAuthService = Depends(OAuthService.create),
    roles_service: RolesService = Depends(RolesService.create),
):
    # Decode the token
    decoded_token = oauth_service.decode_token(token_refresh_request.refresh_token)

    # Validate the token and fetch roles
    validated_token = roles_service.get_roles_for_user(
        user_service.get_user_by_username(decoded_token.sub)
    )

    # Generate new tokens
    tokens = oauth_service.generate_tokens(
        username=decoded_token.sub,
        roles=validated_token,
    )

    return tokens
