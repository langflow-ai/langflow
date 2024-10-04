import datetime
import secrets
import threading
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Session, select

from langflow.services.database.models.api_key import ApiKey, ApiKeyCreate, ApiKeyRead, UnmaskedApiKeyRead

if TYPE_CHECKING:
    from sqlmodel.sql.expression import SelectOfScalar


def get_api_keys(session: Session, user_id: UUID) -> list[ApiKeyRead]:
    query: SelectOfScalar = select(ApiKey).where(ApiKey.user_id == user_id)
    api_keys = session.exec(query).all()
    return [ApiKeyRead.model_validate(api_key) for api_key in api_keys]


def create_api_key(session: Session, api_key_create: ApiKeyCreate, user_id: UUID) -> UnmaskedApiKeyRead:
    # Generate a random API key with 32 bytes of randomness
    generated_api_key = f"sk-{secrets.token_urlsafe(32)}"

    api_key = ApiKey(
        api_key=generated_api_key,
        name=api_key_create.name,
        user_id=user_id,
        created_at=api_key_create.created_at or datetime.datetime.now(datetime.timezone.utc),
    )

    session.add(api_key)
    session.commit()
    session.refresh(api_key)
    unmasked = UnmaskedApiKeyRead.model_validate(api_key, from_attributes=True)
    unmasked.api_key = generated_api_key
    return unmasked


def delete_api_key(session: Session, api_key_id: UUID) -> None:
    api_key = session.get(ApiKey, api_key_id)
    if api_key is None:
        msg = "API Key not found"
        raise ValueError(msg)
    session.delete(api_key)
    session.commit()


def check_key(session: Session, api_key: str) -> ApiKey | None:
    """Check if the API key is valid."""
    query: SelectOfScalar = select(ApiKey).where(ApiKey.api_key == api_key)
    api_key_object: ApiKey | None = session.exec(query).first()
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

    with Session(session.get_bind()) as new_session:
        new_api_key = new_session.get(ApiKey, api_key.id)
        if new_api_key is None:
            msg = "API Key not found"
            raise ValueError(msg)
        new_api_key.total_uses += 1
        new_api_key.last_used_at = datetime.datetime.now(datetime.timezone.utc)
        new_session.add(new_api_key)
        new_session.commit()
    return new_api_key
