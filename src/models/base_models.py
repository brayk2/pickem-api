from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseDto(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, from_attributes=True, alias_generator=to_camel
    )
