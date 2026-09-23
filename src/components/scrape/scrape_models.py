from pydantic import BaseModel


class GenericResponse(BaseModel):
    error: bool
    message: str
