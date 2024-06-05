import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field, field_serializer, field_validator

if TYPE_CHECKING:
    from langflow.schema import Record


class TransactionModel(BaseModel):
    index: Optional[int] = Field(default=None)
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, alias="timestamp")
    flow_id: str
    source: str
    target: str
    target_args: dict
    status: str
    error: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True

    # validate target_args in case it is a JSON
    @field_validator("target_args", mode="before")
    def validate_target_args(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_serializer("target_args")
    def serialize_target_args(v):
        if isinstance(v, dict):
            return json.dumps(v)
        return v


class TransactionModelResponse(BaseModel):
    index: Optional[int] = Field(default=None)
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, alias="timestamp")
    flow_id: str
    source: str
    target: str
    target_args: dict
    status: str
    error: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True

    # validate target_args in case it is a JSON
    @field_validator("target_args", mode="before")
    def validate_target_args(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("index", mode="before")
    def validate_id(cls, v):
        if isinstance(v, float):
            try:
                return int(v)
            except ValueError:
                return None
        return v


class MessageModel(BaseModel):
    index: Optional[int] = Field(default=None)
    flow_id: Optional[str] = Field(default=None, alias="flow_id")
    timestamp: datetime = Field(default_factory=datetime.now)
    sender: str
    sender_name: str
    session_id: str
    message: str
    artifacts: dict

    class Config:
        from_attributes = True
        populate_by_name = True

    @field_validator("artifacts", mode="before")
    def validate_target_args(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @classmethod
    def from_record(cls, record: "Record", flow_id: Optional[str] = None):
        # first check if the record has all the required fields
        if not record.data or ("sender" not in record.data and "sender_name" not in record.data):
            raise ValueError("The record does not have the required fields 'sender' and 'sender_name' in the data.")
        return cls(
            sender=record.sender,
            sender_name=record.sender_name,
            message=record.text,
            session_id=record.session_id,
            artifacts=record.artifacts or {},
            timestamp=record.timestamp,
            flow_id=flow_id,
        )


class MessageModelResponse(MessageModel):
    index: Optional[int] = Field(default=None)

    @field_validator("artifacts", mode="before")
    def serialize_artifacts(v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("index", mode="before")
    def validate_id(cls, v):
        if isinstance(v, float):
            try:
                return int(v)
            except ValueError:
                return None
        return v


class MessageModelRequest(MessageModel):
    message: str = Field(default="")
    sender: str = Field(default="")
    sender_name: str = Field(default="")
    session_id: str = Field(default="")


class VertexBuildModel(BaseModel):
    index: Optional[int] = Field(default=None, alias="index", exclude=True)
    id: Optional[str] = Field(default=None, alias="id")
    flow_id: str
    valid: bool
    params: Any
    data: dict
    artifacts: dict
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True
        populate_by_name = True

    @field_serializer("data", "artifacts")
    def serialize_dict(v):
        if isinstance(v, dict):
            # check if the value of each key is a BaseModel or a list of BaseModels
            for key, value in v.items():
                if isinstance(value, BaseModel):
                    v[key] = value.model_dump()
                elif isinstance(value, list) and all(isinstance(i, BaseModel) for i in value):
                    v[key] = [i.model_dump() for i in value]
            return json.dumps(v)
        elif isinstance(v, BaseModel):
            return v.model_dump_json()
        return v

    @field_validator("params", mode="before")
    def validate_params(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v

    @field_serializer("params")
    def serialize_params(v):
        if isinstance(v, list) and all(isinstance(i, BaseModel) for i in v):
            return json.dumps([i.model_dump() for i in v])
        return v

    @field_validator("data", mode="before")
    def validate_data(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("artifacts", mode="before")
    def validate_artifacts(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        elif isinstance(v, BaseModel):
            return v.model_dump()
        return v


class VertexBuildResponseModel(VertexBuildModel):
    @field_serializer("data", "artifacts")
    def serialize_dict(v):
        return v


def to_map(value: dict):
    keys = list(value.keys())
    values = list(value.values())
    return {"key": keys, "value": values}


class VertexBuildMapModel(BaseModel):
    vertex_builds: dict[str, list[VertexBuildResponseModel]]

    @classmethod
    def from_list_of_dicts(cls, vertex_build_dicts):
        vertex_build_map = {}
        for vertex_build_dict in vertex_build_dicts:
            vertex_build = VertexBuildResponseModel(**vertex_build_dict)
            if vertex_build.id not in vertex_build_map:
                vertex_build_map[vertex_build.id] = []
            vertex_build_map[vertex_build.id].append(vertex_build)
        return cls(vertex_builds=vertex_build_map)
