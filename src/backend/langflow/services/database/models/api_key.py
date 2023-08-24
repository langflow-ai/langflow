from sqlmodel import Field
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime
from langflow.services.database.models.base import SQLModelSerializable, SQLModel


class ApiKeyBase(SQLModelSerializable):
    api_key: str = Field(index=True, unique=True)
    name: str = Field()
    create_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = Field()


class ApiKey(ApiKeyBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)


class ApiKeyCreate(SQLModel):
    name: str = Field()


class ApiKeyRead(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    api_key: str = Field(index=True, unique=True)
    name: str = Field()
    create_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = Field()
