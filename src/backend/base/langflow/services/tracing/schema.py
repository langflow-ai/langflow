from pydantic import BaseModel, field_serializer
from pydantic.v1 import BaseModel as V1BaseModel

from langflow.schema.log import LoggableType


class Log(BaseModel):
    name: str
    message: LoggableType
    type: str

    @field_serializer("message")
    def serialize_message(self, value):
        # We need to make sure everything inside the message has been serialized
        if isinstance(value, dict):
            return {key: self.serialize_message(value[key]) for key in value}
        if isinstance(value, list):
            return [self.serialize_message(item) for item in value]
        # To json is for LangChain Serializable objects
        if hasattr(value, "dict") and isinstance(value, V1BaseModel):
            # This is for Pydantic V1 models
            return value.dict()
        if hasattr(value, "to_json"):
            return value.to_json()
        if isinstance(value, BaseModel):
            return value.model_dump(exclude_none=True)
        return value
