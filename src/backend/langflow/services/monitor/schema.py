import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, validator


class TransactionModel(BaseModel):
    id: Optional[int] = Field(default=None, alias="id")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, alias="timestamp")
    source: str
    target: str
    target_args: dict
    status: str
    error: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True

    # validate target_args in case it is a JSON
    @validator("target_args", pre=True)
    def validate_target_args(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class MessageModel(BaseModel):
    id: Optional[int] = Field(default=None, alias="id")
    timestamp: datetime = Field(default_factory=datetime.now)
    sender_type: str
    sender_name: str
    session_id: str
    message: str
    artifacts: dict

    class Config:
        from_attributes = True
        populate_by_name = True

    @validator("artifacts", pre=True)
    def validate_target_args(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class VertexBuildModel(BaseModel):
    index: Optional[int] = Field(default=None, alias="index")
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

    @validator("params", pre=True)
    def validate_params(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v

    @validator("data", pre=True)
    def validate_data(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @validator("artifacts", pre=True)
    def validate_artifacts(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
