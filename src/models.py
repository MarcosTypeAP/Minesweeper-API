from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class FromDBModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )


class User(FromDBModel):
    username: str
