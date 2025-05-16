from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class ApiKeyBase(BaseModel):
    name: str | None = None
    last_used_at: datetime | None = None
    total_uses: int = 0
    is_active: bool = True


class ApiKeyRead(ApiKeyBase):
    id: str
    api_key: str
    user_id: str
    created_at: datetime

    @field_validator("api_key")
    @classmethod
    def mask_api_key(cls, v: str) -> str:
        return f"{v[:8]}{'*' * (len(v) - 8)}"


class ApiKeysResponse(BaseModel):
    total_count: int
    user_id: UUID
    api_keys: list[ApiKeyRead]


class ApiKeyCreateRequest(BaseModel):
    api_key: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
