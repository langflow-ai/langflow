from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from langflow.services.auth import utils as auth_utils
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.credential import Credential, CredentialCreate, CredentialRead, CredentialUpdate
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session, get_settings_service
from sqlmodel import Session, select

router = APIRouter(prefix="/credentials", tags=["Credentials"])


@router.post("/", response_model=CredentialRead, status_code=201)
def create_credential(
    *,
    session: Session = Depends(get_session),
    credential: CredentialCreate,
    current_user: User = Depends(get_current_active_user),
    settings_service=Depends(get_settings_service),
):
    """Create a new credential."""
    try:
        # check if credential name already exists
        credential_exists = session.exec(
            select(Credential).where(Credential.name == credential.name, Credential.user_id == current_user.id)
        ).first()
        if credential_exists:
            raise HTTPException(status_code=400, detail="Credential name already exists")

        db_credential = Credential.model_validate(credential, from_attributes=True)
        if not db_credential.value:
            raise HTTPException(status_code=400, detail="Credential value cannot be empty")
        encrypted = auth_utils.encrypt_api_key(db_credential.value, settings_service=settings_service)
        db_credential.value = encrypted
        db_credential.user_id = current_user.id
        session.add(db_credential)
        session.commit()
        session.refresh(db_credential)
        return db_credential
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[CredentialRead], status_code=200)
def read_credentials(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    """Read all credentials."""
    try:
        credentials = session.exec(select(Credential).where(Credential.user_id == current_user.id)).all()
        return credentials
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{credential_id}", response_model=CredentialRead, status_code=200)
def update_credential(
    *,
    session: Session = Depends(get_session),
    credential_id: UUID,
    credential: CredentialUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update a credential."""
    try:
        db_credential = session.exec(
            select(Credential).where(Credential.id == credential_id, Credential.user_id == current_user.id)
        ).first()
        if not db_credential:
            raise HTTPException(status_code=404, detail="Credential not found")

        credential_data = credential.model_dump(exclude_unset=True)
        for key, value in credential_data.items():
            setattr(db_credential, key, value)
        db_credential.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(db_credential)
        return db_credential
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
