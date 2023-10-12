from pydantic import BaseModel


class ApiQuota(BaseModel):
    used: float
    remaining: float
