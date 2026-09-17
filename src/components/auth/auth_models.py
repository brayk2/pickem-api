from pydantic import BaseModel, Field, EmailStr

from src.models.base_models import BaseDto


# Pydantic models
class PasswordResetRequestBody(BaseDto):
    email: EmailStr


class PasswordResetConfirmBody(BaseDto):
    token: str
    new_password: str = Field(min_length=8)


class PasswordResetRequestResponse(BaseDto):
    message: str


class PasswordResetConfirmResponse(BaseDto):
    message: str


class PasswordResetErrorResponse(BaseDto):
    detail: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    username: str
    password: str
