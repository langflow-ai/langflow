import json
from datetime import datetime
from typing import Optional

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
        orm_mode = True
        allow_population_by_field_name = True

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
        orm_mode = True
        allow_population_by_field_name = True

    @validator("artifacts", pre=True)
    def validate_target_args(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
