import datetime
import secrets
import threading
from uuid import UUID
from typing import List, Optional
from langflow.services.database.utils import session_getter
from langflow.services.utils import get_db_manager
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
    generated_api_key = f"lf-{secrets.token_urlsafe(32)}"

    api_key = ApiKey(
        api_key=generated_api_key,
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


def check_key(session: Session, api_key: str) -> Optional[ApiKey]:
    """Check if the API key is valid."""
    query = select(ApiKey).where(ApiKey.api_key == api_key)
    api_key_object: Optional[ApiKey] = session.exec(query).first()
    if api_key_object is not None:
        threading.Thread(
            target=update_total_uses,
            args=(
                session,
                api_key_object,
            ),
        ).start()
    return api_key_object


def update_total_uses(session, api_key: ApiKey):
    """Update the total uses and last used at."""
    # This is running in a separate thread to avoid slowing down the request
    # but session is not thread safe so we need to create a new session
    db_manager = get_db_manager()
    with session_getter(db_manager) as new_session:
        api_key = new_session.get(ApiKey, api_key.id)
        api_key.total_uses += 1
        api_key.last_used_at = datetime.datetime.now(datetime.timezone.utc)
        new_session.add(api_key)
        new_session.commit()
    return api_key
