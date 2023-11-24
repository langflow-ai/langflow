from typing import TYPE_CHECKING, Union
from uuid import UUID

from fastapi import Depends
from sqlmodel import Session

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.credential.model import Credential
from langflow.services.deps import get_session

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class CredentialService(Service):
    name = "credential_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service

    def get_credential(self, user_id: Union[UUID, str], name: str, session: Session = Depends(get_session)) -> str:
        # we get the credential from the database
        credential = session.query(Credential).filter(Credential.user_id == user_id, Credential.name == name).first()
        # we decrypt the value
        if not credential:
            raise ValueError(f"{name} credential not found.")
        decrypted = auth_utils.decrypt_api_key(credential.value, settings_service=self.settings_service)
        return decrypted
