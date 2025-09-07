from pydantic import BaseModel
from strenum import StrEnum


class ActionType(StrEnum):
    Lambda = "LAMBDA"
    StepFunction = "STEP_FUNCTION"


class CreateActionRequest(BaseModel):
    name: str
    type: ActionType
    arn: str
