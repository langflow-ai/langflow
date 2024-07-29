import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, field_validator

from langflow.schema.message import Message


class DefaultModel(BaseModel):
    class Config:
        from_attributes = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    def json(self, **kwargs):
        # Usa a função de serialização personalizada
        return super().model_dump_json(**kwargs, encoder=self.custom_encoder)

    @staticmethod
    def custom_encoder(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


class TransactionModel(DefaultModel):
    index: int | None = Field(default=None)
    timestamp: datetime | None = Field(default_factory=datetime.now, alias="timestamp")
    vertex_id: str
    target_id: str | None = None
    inputs: dict
    outputs: dict | None = None
    status: str
    error: str | None = None
    flow_id: str | None = Field(default=None, alias="flow_id")

    # validate target_args in case it is a JSON
    @field_validator("outputs", "inputs", mode="before")
    def validate_target_args(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_serializer("outputs", "inputs")
    def serialize_target_args(v):
        if isinstance(v, dict):
            return json.dumps(v)
        return v


class TransactionModelResponse(DefaultModel):
    index: int | None = Field(default=None)
    timestamp: datetime | None = Field(default_factory=datetime.now, alias="timestamp")
    vertex_id: str
    inputs: dict
    outputs: dict | None = None
    status: str
    error: str | None = None
    flow_id: str | None = Field(default=None, alias="flow_id")
    source: str | None = None
    target: str | None = None

    # validate target_args in case it is a JSON
    @field_validator("outputs", "inputs", mode="before")
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


class DuckDbMessageModel(DefaultModel):
    index: int | None = Field(default=None, alias="index")
    flow_id: str | None = Field(default=None, alias="flow_id")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sender: str
    sender_name: str
    session_id: str
    text: str
    files: list[str] = []

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, v):
        if isinstance(v, str):
            v = json.loads(v)
        return v

    @field_serializer("timestamp")
    @classmethod
    def serialize_timestamp(cls, v):
        v = v.replace(microsecond=0)
        return v.strftime("%Y-%m-%d %H:%M:%S")

    @field_serializer("files")
    @classmethod
    def serialize_files(cls, v):
        if isinstance(v, list):
            return json.dumps(v)
        return v

    @classmethod
    def from_message(cls, message: Message, flow_id: str | None = None):
        # first check if the record has all the required fields
        if message.text is None or not message.sender or not message.sender_name:
            raise ValueError("The message does not have the required fields (text, sender, sender_name).")
        return cls(
            sender=message.sender,
            sender_name=message.sender_name,
            text=message.text,
            session_id=message.session_id,
            files=message.files or [],
            timestamp=message.timestamp,
            flow_id=flow_id,
        )


class MessageModel(DefaultModel):
    id: str | UUID | None = Field(default=None)
    flow_id: UUID | None = Field(default=None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sender: str
    sender_name: str
    session_id: str
    text: str
    files: list[str] = []

    @field_validator("files", mode="before")
    @classmethod
    def validate_files(cls, v):
        if isinstance(v, str):
            v = json.loads(v)
        return v

    @field_serializer("timestamp")
    @classmethod
    def serialize_timestamp(cls, v):
        v = v.replace(microsecond=0)
        return v.strftime("%Y-%m-%d %H:%M:%S")

    @field_serializer("files")
    @classmethod
    def serialize_files(cls, v):
        if isinstance(v, list):
            return json.dumps(v)
        return v

    @classmethod
    def from_message(cls, message: Message, flow_id: str | None = None):
        # first check if the record has all the required fields
        if message.text is None or not message.sender or not message.sender_name:
            raise ValueError("The message does not have the required fields (text, sender, sender_name).")
        return cls(
            sender=message.sender,
            sender_name=message.sender_name,
            text=message.text,
            session_id=message.session_id,
            files=message.files or [],
            timestamp=message.timestamp,
            flow_id=flow_id,
        )


class MessageModelResponse(MessageModel):
    pass


class MessageModelRequest(MessageModel):
    text: str = Field(default="")
    sender: str = Field(default="")
    sender_name: str = Field(default="")
    session_id: str = Field(default="")


class VertexBuildModel(DefaultModel):
    index: int | None = Field(default=None, alias="index", exclude=True)
    id: str | None = Field(default=None, alias="id")
    flow_id: str
    valid: bool
    params: Any
    data: dict
    artifacts: dict
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_serializer("data", "artifacts")
    def serialize_dict(v):
        if isinstance(v, dict):
            # check if the value of each key is a BaseModel or a list of BaseModels
            for key, value in v.items():
                if isinstance(value, BaseModel):
                    v[key] = value.model_dump()
                elif isinstance(value, list) and all(isinstance(i, BaseModel) for i in value):
                    v[key] = [i.model_dump() for i in value]
            return json.dumps(v, default=str)
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
