import secrets
from uuid import UUID
from typing import List
from langflow.services.auth.utils import get_password_hash
from sqlmodel import Session, select
from langflow.services.database.models.api_key import (
    ApiKey,
    ApiKeyCreate,
    UnmaskedApiKeyRead,
    ApiKeyRead,
)


def get_api_keys(session: Session, user_id: UUID) -> List[ApiKeyRead]:
    query = select(ApiKey).where(ApiKey.user_id == user_id)
    api_keys = session.exec(query).all()
    return [ApiKeyRead.from_orm(api_key) for api_key in api_keys]


def create_api_key(
    session: Session, api_key_create: ApiKeyCreate, user_id: UUID
) -> UnmaskedApiKeyRead:
    # Generate a random API key with 32 bytes of randomness
    generated_api_key = secrets.token_urlsafe(32)

    # hash the API key
    hashed = get_password_hash(generated_api_key)
    # Use the generated key to create the ApiKey object
    masked_api_key = f"{'*' * 10}{generated_api_key[-4:]}"
    api_key = ApiKey(
        api_key=masked_api_key,
        hashed_api_key=hashed,
        name=api_key_create.name,
        user_id=user_id,
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    unmasked = UnmaskedApiKeyRead.from_orm(api_key)
    unmasked.api_key = generated_api_key
    return unmasked


def delete_api_key(session: Session, api_key_id: UUID) -> None:
    api_key = session.get(ApiKey, api_key_id)
    if api_key is None:
        raise ValueError("API Key not found")
    session.delete(api_key)
    session.commit()
