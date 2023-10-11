from pydantic import validator
from sqlmodel import Field, Relationship
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from langflow.services.database.models.base import SQLModelSerializable

if TYPE_CHECKING:
    from langflow.services.database.models.user import User


class ApiKeyBase(SQLModelSerializable):
    name: Optional[str] = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = Field(default=None, nullable=True)
    total_uses: int = Field(default=0)
    is_active: bool = Field(default=True)


class ApiKey(ApiKeyBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)

    api_key: str = Field(index=True, unique=True)
    # User relationship
    # Delete API keys when user is deleted
    user_id: UUID = Field(index=True, foreign_key="user.id")
    user: "User" = Relationship(
        back_populates="api_keys",
    )


class ApiKeyCreate(ApiKeyBase):
    api_key: Optional[str] = None
    user_id: Optional[UUID] = None


class UnmaskedApiKeyRead(ApiKeyBase):
    id: UUID
    api_key: str = Field()
    user_id: UUID = Field()


class ApiKeyRead(ApiKeyBase):
    id: UUID
    api_key: str = Field()
    user_id: UUID = Field()

    @validator("api_key", always=True)
    def mask_api_key(cls, v):
        # This validator will always run, and will mask the API key
        return f"{v[:8]}{'*' * (len(v) - 8)}"
