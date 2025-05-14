from pydantic import BaseModel, field_validator
from uuid import UUID
from typing import Optional
from datetime import datetime

class ApiKeyBase(BaseModel):
    name: Optional[str] = None
    last_used_at: Optional[datetime] = None
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

class ApiKeyResponse(BaseModel):
    id: str
    api_key: str
    name: str
    created_at: str
    last_used_at: str

class ApiKeysResponse(BaseModel):
    total_count: int
    user_id: UUID
    api_keys: list[ApiKeyRead]

class CreateApiKeyRequest(BaseModel):
    name: str

class ApiKeyCreateRequest(BaseModel):
    api_key: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
