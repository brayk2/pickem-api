from pydantic import BaseModel, Field

from src.models.base_models import BaseDto


# Pydantic models
class TokenResponse(BaseDto):
    token_type: str = Field(alias="tokenType")
    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    expiration: float = Field(alias="exp")


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    username: str
    password: str


class DecodedToken(BaseModel):
    sub: str
    roles: list[str]
    exp: float | None = None  # Optional expiration time

    @classmethod
    def from_dict(cls, data: dict) -> "DecodedToken":
        return cls(**data)

    def to_dict(self) -> dict:
        return self.model_dump()

    @property
    def is_admin(self):
        return "admin" in self.roles

    @property
    def is_commissioner(self):
        return "commissioner" in self.roles
