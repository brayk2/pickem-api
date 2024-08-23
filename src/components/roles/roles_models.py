from pydantic import BaseModel, Field, ConfigDict


class RoleCreateDto(BaseModel):
    name: str = Field(..., example="admin")
    description: str | None = Field(
        None, example="Administrator role with full permissions"
    )


class RoleDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None


class AddUserToRoleDto(BaseModel):
    username: str = Field(..., example="johndoe")
    role: str = Field(..., example="admin")
