from pydantic import BaseModel
from uuid import UUID

from langflow.services.database.models.api_key.model import ApiKeyRead

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
