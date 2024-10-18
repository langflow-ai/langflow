from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import Depends
from loguru import logger
from sqlmodel import Session, select

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable, VariableCreate, VariableUpdate
from langflow.services.deps import get_session
from langflow.services.variable.base import VariableService
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from langflow.services.settings.service import SettingsService


class DatabaseVariableService(VariableService, Service):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    def initialize_user_variables(self, user_id: UUID | str, session: Session = Depends(get_session)):
        if not self.settings_service.settings.store_environment_variables:
            logger.info("Skipping environment variable storage.")
            return

        logger.info("Storing environment variables in the database.")
        for var_name in self.settings_service.settings.variables_to_get_from_environment:
            if var_name in os.environ and os.environ[var_name].strip():
                value = os.environ[var_name].strip()
                query = select(Variable).where(Variable.user_id == user_id, Variable.name == var_name)
                existing = session.exec(query).first()
                try:
                    if existing:
                        self.update_variable(user_id, var_name, value, session)
                    else:
                        self.create_variable(
                            user_id=user_id,
                            name=var_name,
                            value=value,
                            default_fields=[],
                            _type=CREDENTIAL_TYPE,
                            session=session,
                        )
                    logger.info(f"Processed {var_name} variable from environment.")
                except Exception as e:  # noqa: BLE001
                    logger.exception(f"Error processing {var_name} variable: {e!s}")

    def get_variable(
        self,
        user_id: UUID | str,
        name: str,
        field: str,
        session: Session = Depends(get_session),
    ) -> str:
        # we get the credential from the database
        # credential = session.query(Variable).filter(Variable.user_id == user_id, Variable.name == name).first()
        variable = session.exec(select(Variable).where(Variable.user_id == user_id, Variable.name == name)).first()

        if not variable or not variable.value:
            msg = f"{name} variable not found."
            raise ValueError(msg)

        if variable.type == CREDENTIAL_TYPE and field == "session_id":
            msg = (
                f"variable {name} of type 'Credential' cannot be used in a Session ID field "
                "because its purpose is to prevent the exposure of values."
            )
            raise TypeError(msg)

        # we decrypt the value
        return auth_utils.decrypt_api_key(variable.value, settings_service=self.settings_service)

    def get_all(self, user_id: UUID | str, session: Session = Depends(get_session)) -> list[Variable | None]:
        return list(session.exec(select(Variable).where(Variable.user_id == user_id)).all())

    def list_variables(self, user_id: UUID | str, session: Session = Depends(get_session)) -> list[str | None]:
        variables = self.get_all(user_id=user_id, session=session)
        return [variable.name for variable in variables if variable]

    def update_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        session: Session = Depends(get_session),
    ):
        variable = session.exec(select(Variable).where(Variable.user_id == user_id, Variable.name == name)).first()
        if not variable:
            msg = f"{name} variable not found."
            raise ValueError(msg)
        encrypted = auth_utils.encrypt_api_key(value, settings_service=self.settings_service)
        variable.value = encrypted
        session.add(variable)
        session.commit()
        session.refresh(variable)
        return variable

    def update_variable_fields(
        self,
        user_id: UUID | str,
        variable_id: UUID | str,
        variable: VariableUpdate,
        session: Session = Depends(get_session),
    ):
        query = select(Variable).where(Variable.id == variable_id, Variable.user_id == user_id)
        db_variable = session.exec(query).one()
        db_variable.updated_at = datetime.now(timezone.utc)

        variable.value = variable.value or ""
        encrypted = auth_utils.encrypt_api_key(variable.value, settings_service=self.settings_service)
        variable.value = encrypted

        variable_data = variable.model_dump(exclude_unset=True)
        for key, value in variable_data.items():
            setattr(db_variable, key, value)

        session.add(db_variable)
        session.commit()
        session.refresh(db_variable)
        return db_variable

    def delete_variable(
        self,
        user_id: UUID | str,
        name: str,
        session: Session = Depends(get_session),
    ):
        stmt = select(Variable).where(Variable.user_id == user_id).where(Variable.name == name)
        variable = session.exec(stmt).first()
        if not variable:
            msg = f"{name} variable not found."
            raise ValueError(msg)
        session.delete(variable)
        session.commit()

    def delete_variable_by_id(self, user_id: UUID | str, variable_id: UUID, session: Session):
        variable = session.exec(select(Variable).where(Variable.user_id == user_id, Variable.id == variable_id)).first()
        if not variable:
            msg = f"{variable_id} variable not found."
            raise ValueError(msg)
        session.delete(variable)
        session.commit()

    def create_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        default_fields: Sequence[str] = (),
        _type: str = GENERIC_TYPE,
        session: Session = Depends(get_session),
    ):
        variable_base = VariableCreate(
            name=name,
            type=_type,
            value=auth_utils.encrypt_api_key(value, settings_service=self.settings_service),
            default_fields=list(default_fields),
        )
        variable = Variable.model_validate(variable_base, from_attributes=True, update={"user_id": user_id})
        session.add(variable)
        session.commit()
        session.refresh(variable)
        return variable
