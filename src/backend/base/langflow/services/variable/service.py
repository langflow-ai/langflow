from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from loguru import logger
from sqlmodel import select
from typing_extensions import override

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable, VariableCreate, VariableRead, VariableUpdate
from langflow.services.variable.base import VariableService
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.settings.service import SettingsService


class DatabaseVariableService(VariableService, Service):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    async def initialize_user_variables(self, user_id: UUID | str, session: AsyncSession) -> None:
        if not self.settings_service.settings.store_environment_variables:
            logger.debug("Skipping environment variable storage.")
            return

        logger.debug("Storing environment variables in the database.")
        for var_name in self.settings_service.settings.variables_to_get_from_environment:
            if var_name in os.environ and os.environ[var_name].strip():
                value = os.environ[var_name].strip()
                query = select(Variable).where(Variable.user_id == user_id, Variable.name == var_name)
                existing = (await session.exec(query)).first()
                try:
                    if existing:
                        await self.update_variable(user_id, var_name, value, session)
                    else:
                        await self.create_variable(
                            user_id=user_id,
                            name=var_name,
                            value=value,
                            default_fields=[],
                            type_=CREDENTIAL_TYPE,
                            session=session,
                        )
                    logger.debug(f"Processed {var_name} variable from environment.")
                except Exception as e:  # noqa: BLE001
                    logger.exception(f"Error processing {var_name} variable: {e!s}")

    async def get_variable(
        self,
        user_id: UUID | str,
        name: str,
        field: str,
        session: AsyncSession,
    ) -> str:
        # we get the credential from the database
        # credential = session.query(Variable).filter(Variable.user_id == user_id, Variable.name == name).first()
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.name == name)
        variable = (await session.exec(stmt)).first()

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

    async def get_all(self, user_id: UUID | str, session: AsyncSession) -> list[VariableRead]:
        stmt = select(Variable).where(Variable.user_id == user_id)
        variables = list((await session.exec(stmt)).all())
        # For variables of type 'Generic', attempt to decrypt the value.
        # If decryption fails, assume the value is already plaintext.
        variables_read = []
        for variable in variables:
            value = None
            if variable.type == GENERIC_TYPE:
                try:
                    value = auth_utils.decrypt_api_key(variable.value, settings_service=self.settings_service)
                except Exception as e:  # noqa: BLE001
                    logger.debug(
                        f"Decryption of {variable.type} failed for variable '{variable.name}': {e}. Assuming plaintext."
                    )
                    value = variable.value
            variable_read = VariableRead.model_validate(variable, from_attributes=True)
            variable_read.value = value
            variables_read.append(variable_read)
        return variables_read

    async def list_variables(self, user_id: UUID | str, session: AsyncSession) -> list[str | None]:
        variables = await self.get_all(user_id=user_id, session=session)
        return [variable.name for variable in variables if variable]

    async def update_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        session: AsyncSession,
    ):
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.name == name)
        variable = (await session.exec(stmt)).first()
        if not variable:
            msg = f"{name} variable not found."
            raise ValueError(msg)
        encrypted = auth_utils.encrypt_api_key(value, settings_service=self.settings_service)
        variable.value = encrypted
        session.add(variable)
        await session.commit()
        await session.refresh(variable)
        return variable

    async def update_variable_fields(
        self,
        user_id: UUID | str,
        variable_id: UUID | str,
        variable: VariableUpdate,
        session: AsyncSession,
    ):
        query = select(Variable).where(Variable.id == variable_id, Variable.user_id == user_id)
        db_variable = (await session.exec(query)).one()
        db_variable.updated_at = datetime.now(timezone.utc)

        variable.value = variable.value or ""
        encrypted = auth_utils.encrypt_api_key(variable.value, settings_service=self.settings_service)
        variable.value = encrypted

        variable_data = variable.model_dump(exclude_unset=True)
        for key, value in variable_data.items():
            setattr(db_variable, key, value)

        session.add(db_variable)
        await session.commit()
        await session.refresh(db_variable)
        return db_variable

    @override
    async def delete_variable(
        self,
        user_id: UUID | str,
        name: str,
        session: AsyncSession,
    ) -> None:
        stmt = select(Variable).where(Variable.user_id == user_id).where(Variable.name == name)
        variable = (await session.exec(stmt)).first()
        if not variable:
            msg = f"{name} variable not found."
            raise ValueError(msg)
        await session.delete(variable)
        await session.commit()

    @override
    async def delete_variable_by_id(self, user_id: UUID | str, variable_id: UUID, session: AsyncSession) -> None:
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.id == variable_id)
        variable = (await session.exec(stmt)).first()
        if not variable:
            msg = f"{variable_id} variable not found."
            raise ValueError(msg)
        await session.delete(variable)
        await session.commit()

    async def create_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        *,
        default_fields: Sequence[str] = (),
        type_: str = CREDENTIAL_TYPE,
        session: AsyncSession,
    ):
        variable_base = VariableCreate(
            name=name,
            type=type_,
            value=auth_utils.encrypt_api_key(value, settings_service=self.settings_service),
            default_fields=list(default_fields),
        )
        variable = Variable.model_validate(variable_base, from_attributes=True, update={"user_id": user_id})
        session.add(variable)
        await session.commit()
        await session.refresh(variable)
        return variable
