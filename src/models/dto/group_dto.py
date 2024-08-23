from pydantic import BaseModel


class CreateGroupRequest(BaseModel):
    name: str
    description: str


class CreateGroupResponse(BaseModel):
    id: int
    name: str
    description: str


class GroupDto(BaseModel):
    name: str
    description: str
