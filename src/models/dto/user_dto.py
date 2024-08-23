from pydantic import BaseModel, ConfigDict


class CreateUserRequest(BaseModel):
    password: str
    email: str


class CreateUserResponse(BaseModel):
    email: str
