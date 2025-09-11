from pydantic import EmailStr, ConfigDict, Field, computed_field

from src.models.base_models import BaseDto


class CreateUserDto(BaseDto):
    username: str
    email: str
    password: str
    first_name: str | None = None
    last_name: str | None = None


class UpdateUserRequest(BaseDto):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class UpdateUserPasswordRequest(BaseDto):
    old_password: str
    new_password: str


class AddRoleDto(BaseDto):
    username: str
    role: str


class UserDto(BaseDto):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    first_name: str | None = Field(default=None)
    last_name: str | None = Field(default=None)
    email: EmailStr
    groups: list[str] | None = Field(exclude=False, default_factory=list)

    @computed_field
    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @computed_field(alias="isAdmin")
    @property
    def is_admin(self) -> bool:
        return "admin" in self.groups

    @computed_field(alias="isCommissioner")
    @property
    def is_commissioner(self) -> bool:
        return "commissioner" in self.groups
