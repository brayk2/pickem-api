from fastapi import APIRouter, Depends
from starlette import status

from src.security.security_models import TokenResponse
from src.components.auth.auth_models import (
    LoginRequest,
    TokenRefreshRequest,
    PasswordResetRequestResponse,
    PasswordResetRequestBody,
    PasswordResetErrorResponse,
    PasswordResetConfirmResponse,
    PasswordResetConfirmBody,
)
from src.components.auth.auth_service import AuthService

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: LoginRequest,
    auth_service: AuthService = Depends(AuthService.create),
):
    return auth_service.login(username=form_data.username, password=form_data.password)


@auth_router.post("/token/refresh", response_model=TokenResponse)
async def refresh_access_token(
    token_refresh_request: TokenRefreshRequest,
    auth_service: AuthService = Depends(AuthService.create),
):
    return auth_service.refresh(refresh_token=token_refresh_request.refresh_token)


@auth_router.post(
    "/token/password-reset/request",
    response_model=PasswordResetRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reset_password_request(
    body: PasswordResetRequestBody,
    auth_service: AuthService = Depends(AuthService.create),
):
    auth_service.request_password_reset(password_reset_request=body)
    return {
        "message": "If an account exists for that email, a password reset link has been sent."
    }


@auth_router.post(
    "/token/password-reset/confirm",
    response_model=PasswordResetConfirmResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": PasswordResetErrorResponse},
    },
)
async def reset_password_confirm(
    body: PasswordResetConfirmBody,
    auth_service: AuthService = Depends(AuthService.create),
):
    return auth_service.confirm_password_reset(password_reset_confirm=body)
