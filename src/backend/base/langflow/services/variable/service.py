from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID

from fastapi import Depends
from sqlmodel import Session, select

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import get_session

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class VariableService(Service):
    name = "variable_service"

    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service

    def get_variable(self, user_id: Union[UUID, str], name: str, session: Session = Depends(get_session)) -> str:
        # we get the credential from the database
        # credential = session.query(Variable).filter(Variable.user_id == user_id, Variable.name == name).first()
        variable = session.exec(select(Variable).where(Variable.user_id == user_id, Variable.name == name)).first()
        # we decrypt the value
        if not variable or not variable.value:
            raise ValueError(f"{name} variable not found.")
        decrypted = auth_utils.decrypt_api_key(variable.value, settings_service=self.settings_service)
        return decrypted

    def list_variables(self, user_id: Union[UUID, str], session: Session = Depends(get_session)) -> list[Optional[str]]:
        variables = session.exec(select(Variable).where(Variable.user_id == user_id)).all()
        return [variable.name for variable in variables]

    def update_variable(
        self, user_id: Union[UUID, str], name: str, value: str, session: Session = Depends(get_session)
    ):
        variable = session.exec(select(Variable).where(Variable.user_id == user_id, Variable.name == name)).first()
        if not variable:
            raise ValueError(f"{name} variable not found.")
        encrypted = auth_utils.encrypt_api_key(value, settings_service=self.settings_service)
        variable.value = encrypted
        session.add(variable)
        session.commit()
        session.refresh(variable)
        return variable

    def delete_variable(self, user_id: Union[UUID, str], name: str, session: Session = Depends(get_session)):
        variable = session.exec(select(Variable).where(Variable.user_id == user_id, Variable.name == name)).first()
        if not variable:
            raise ValueError(f"{name} variable not found.")
        session.delete(variable)
        session.commit()
        return variable

    def create_variable(
        self, user_id: Union[UUID, str], name: str, value: str, session: Session = Depends(get_session)
    ):
        variable = Variable(
            user_id=user_id, name=name, value=auth_utils.encrypt_api_key(value, settings_service=self.settings_service)
        )
        session.add(variable)
        session.commit()
        session.refresh(variable)
        return variable
