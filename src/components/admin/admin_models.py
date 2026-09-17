from pydantic import BaseModel
from strenum import StrEnum


class SetCurrentWeekRequest(BaseModel):
    week: int


class SetCurrentWeekResponse(BaseModel):
    message: str
    week: int


class ApiQuota(BaseModel):
    used: float
    remaining: float


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


from strenum import StrEnum


class ActionType(StrEnum):
    Lambda = "LAMBDA"
    StepFunction = "STEP_FUNCTION"


class CreateActionRequest(BaseModel):
    name: str
    type: ActionType
    arn: str
