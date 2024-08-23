from pydantic import BaseModel, EmailStr, ConfigDict, Field, computed_field


class CreateUserDto(BaseModel):
    username: str
    email: str
    password: str
    first_name: str | None = None
    last_name: str | None = None


class UpdateUserRequest(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class UpdateUserPasswordRequest(BaseModel):
    old_password: str
    new_password: str


class AddRoleDto(BaseModel):
    username: str
    role: str


class UserDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    groups: list[str] | None = Field(exclude=True, default_factory=list)

    @computed_field(alias="isAdmin")
    @property
    def is_admin(self) -> bool:
        return "admin" in self.groups

    @computed_field(alias="isCommissioner")
    @property
    def is_commissioner(self) -> bool:
        return "commissioner" in self.groups
