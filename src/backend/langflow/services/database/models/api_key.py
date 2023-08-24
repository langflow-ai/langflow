from sqlmodel import Field
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime
from langflow.services.database.models.base import SQLModelSerializable


class ApiKeyBase(SQLModelSerializable):
    api_key: str = Field(index=True, unique=True)
    name: Optional[str] = Field(index=True)
    create_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = Field(default=None)


class ApiKey(ApiKeyBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)


class ApiKeyCreate(ApiKeyBase):
    pass


class ApiKeyRead(ApiKeyBase):
    id: UUID
