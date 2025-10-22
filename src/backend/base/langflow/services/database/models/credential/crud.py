"""CRUD operations for credentials."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.credential.model import Credential, CredentialCreate, CredentialUpdate
from langflow.services.deps import get_settings_service


async def create_credential(db: AsyncSession, user_id: UUID, credential: CredentialCreate) -> Credential:
    """Create a new credential for a user."""
    settings_service = get_settings_service()

    # Encrypt the credential value
    encrypted_value = auth_utils.encrypt_api_key(credential.value, settings_service=settings_service)

    # Create credential object
    db_credential = Credential(
        name=credential.name,
        provider=credential.provider,
        description=credential.description,
        is_active=credential.is_active,
        encrypted_value=encrypted_value,
        user_id=user_id,
    )

    db.add(db_credential)
    await db.commit()
    await db.refresh(db_credential)

    return db_credential


async def get_credential_by_id(db: AsyncSession, credential_id: UUID, user_id: UUID) -> Credential | None:
    """Get a credential by ID for a specific user."""
    stmt = select(Credential).where(Credential.id == credential_id, Credential.user_id == user_id)
    return (await db.exec(stmt)).first()


async def get_credentials_by_user(db: AsyncSession, user_id: UUID, provider: str | None = None) -> list[Credential]:
    """Get all credentials for a user, optionally filtered by provider."""
    stmt = select(Credential).where(Credential.user_id == user_id)

    if provider:
        stmt = stmt.where(Credential.provider == provider)

    result = await db.exec(stmt)
    return list(result.all())


async def update_credential(
    db: AsyncSession, credential_id: UUID, user_id: UUID, credential_update: CredentialUpdate
) -> Credential:
    """Update a credential."""
    # Get existing credential
    credential = await get_credential_by_id(db, credential_id, user_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    # Update fields
    update_data = credential_update.model_dump(exclude_unset=True)

    # Handle credential value update (re-encrypt if provided)
    if update_data.get("value"):
        settings_service = get_settings_service()
        credential.encrypted_value = auth_utils.encrypt_api_key(update_data["value"], settings_service=settings_service)
        del update_data["value"]  # Remove from update_data since we handled it

    # Update other fields
    for field, value in update_data.items():
        if hasattr(credential, field) and value is not None:
            setattr(credential, field, value)

    credential.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(credential)

    return credential


async def delete_credential(db: AsyncSession, credential_id: UUID, user_id: UUID) -> None:
    """Delete a credential."""
    credential = await get_credential_by_id(db, credential_id, user_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    await db.delete(credential)
    await db.commit()


async def get_credential_value(db: AsyncSession, credential_id: UUID, user_id: UUID) -> str:
    """Get the decrypted credential value."""
    credential = await get_credential_by_id(db, credential_id, user_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    settings_service = get_settings_service()
    return auth_utils.decrypt_api_key(credential.encrypted_value, settings_service=settings_service)


async def increment_credential_usage(db: AsyncSession, credential_id: UUID, user_id: UUID) -> None:
    """Increment usage count and update last_used timestamp."""
    credential = await get_credential_by_id(db, credential_id, user_id)
    if not credential:
        return

    credential.usage_count += 1
    credential.last_used = datetime.now(timezone.utc)

    await db.commit()
