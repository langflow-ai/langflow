from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable, VariableCreate, VariableRead, VariableUpdate
from langflow.services.variable.base import VariableService
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession


class DatabaseVariableService(VariableService, Service):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    async def initialize_user_variables(self, user_id: UUID | str, session: AsyncSession) -> None:
        if not self.settings_service.settings.store_environment_variables:
            await logger.adebug("Skipping environment variable storage.")
            return

        # Import the provider mapping to set default_fields for known providers
        try:
            from lfx.base.models.unified_models import get_model_provider_variable_mapping

            provider_mapping = get_model_provider_variable_mapping()
            # Reverse the mapping to go from variable name to provider
            var_to_provider = {var_name: provider for provider, var_name in provider_mapping.items()}
        except Exception:  # noqa: BLE001
            var_to_provider = {}

        for var_name in self.settings_service.settings.variables_to_get_from_environment:
            # Check if session is still usable before processing each variable
            if not session.is_active:
                await logger.awarning(
                    "Session is no longer active during variable initialization. "
                    "Some environment variables may not have been processed."
                )
                break

            if var_name in os.environ and os.environ[var_name].strip():
                value = os.environ[var_name].strip()

                # Skip placeholder/test values like "dummy" for API key variables only
                # This prevents test environments from overwriting user-configured model provider keys
                is_api_key_variable = var_name in var_to_provider
                if is_api_key_variable and value.lower() == "dummy":
                    await logger.adebug(
                        f"Skipping API key variable {var_name} with placeholder value 'dummy' "
                        "to preserve user configuration"
                    )
                    continue

                query = select(Variable).where(Variable.user_id == user_id, Variable.name == var_name)
                # Set default_fields if this is a known provider variable
                default_fields = []
                try:
                    if is_api_key_variable:
                        provider_name = var_to_provider[var_name]
                        default_fields = [provider_name, "api_key"]
                    existing = (await session.exec(query)).first()
                except Exception as e:  # noqa: BLE001
                    await logger.aexception(f"Error querying {var_name} variable: {e!s}")
                    # If session got rolled back during query, stop processing
                    if not session.is_active:
                        await logger.awarning(
                            f"Session rolled back during {var_name} query. Stopping variable initialization."
                        )
                        break
                    continue

                try:
                    if existing:
                        # Check if the variable has been user-modified (updated_at != created_at)
                        # If so, don't overwrite with environment variable
                        is_user_modified = (
                            existing.updated_at is not None
                            and existing.created_at is not None
                            and existing.updated_at > existing.created_at
                        )

                        if is_user_modified:
                            # Variable was modified by user, don't overwrite with environment variable
                            # Only update default_fields if they're not set
                            if not existing.default_fields and default_fields:
                                variable_update = VariableUpdate(
                                    id=existing.id,
                                    default_fields=default_fields,
                                )
                                await self.update_variable_fields(
                                    user_id=user_id,
                                    variable_id=existing.id,
                                    variable=variable_update,
                                    session=session,
                                )
                            await logger.adebug(
                                f"Skipping update of user-modified variable {var_name} with environment value"
                            )
                        # Variable was not user-modified, safe to update from environment
                        elif not existing.default_fields and default_fields:
                            # Update both value and default_fields
                            variable_update = VariableUpdate(
                                id=existing.id,
                                value=value,
                                default_fields=default_fields,
                            )
                            await self.update_variable_fields(
                                user_id=user_id,
                                variable_id=existing.id,
                                variable=variable_update,
                                session=session,
                            )
                        else:
                            await self.update_variable(user_id, var_name, value, session=session)
                    else:
                        await self.create_variable(
                            user_id=user_id,
                            name=var_name,
                            value=value,
                            default_fields=default_fields,
                            type_=CREDENTIAL_TYPE,
                            session=session,
                        )
                    await logger.adebug(f"Processed {var_name} variable from environment.")
                except Exception as e:  # noqa: BLE001
                    await logger.aexception(f"Error processing {var_name} variable: {e!s}")
                    # If session got rolled back due to error, stop processing
                    if not session.is_active:
                        await logger.awarning(
                            f"Session rolled back after error processing {var_name}. Stopping variable initialization."
                        )
                        break

    async def get_variable_object(
        self,
        user_id: UUID | str,
        name: str,
        session: AsyncSession,
    ) -> Variable:
        # we get the credential from the database
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.name == name)
        variable = (await session.exec(stmt)).first()

        if not variable or not variable.value:
            msg = f"{name} variable not found."
            raise ValueError(msg)

        return variable

    async def get_variable(
        self,
        user_id: UUID | str,
        name: str,
        field: str,
        session: AsyncSession,
    ) -> str:
        # we get the credential from the database
        # credential = session.query(Variable).filter(Variable.user_id == user_id, Variable.name == name).first()
        variable = await self.get_variable_object(user_id, name, session)

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
                    await logger.adebug(
                        f"Decryption of {variable.type} failed for variable '{variable.name}': {e}. Assuming plaintext."
                    )
                    value = variable.value
            variable_read = VariableRead.model_validate(variable, from_attributes=True)
            variable_read.value = value
            variables_read.append(variable_read)
        return variables_read

    async def get_variable_by_id(
        self,
        user_id: UUID | str,
        variable_id: UUID | str,
        session: AsyncSession,
    ) -> Variable:
        query = select(Variable).where(Variable.id == variable_id, Variable.user_id == user_id)
        variable = (await session.exec(query)).first()
        if not variable:
            msg = f"{variable_id} variable not found."
            raise ValueError(msg)
        return variable

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
        # Only encrypt CREDENTIAL_TYPE variables
        if variable.type == CREDENTIAL_TYPE:
            variable.value = auth_utils.encrypt_api_key(value, settings_service=self.settings_service)
        else:
            variable.value = value
        variable.updated_at = datetime.now(timezone.utc)
        session.add(variable)
        await session.flush()
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

        # Use the variable's type if provided, otherwise use the db_variable's type
        variable_type = variable.type or db_variable.type

        # Only process value if it's actually provided (not None)
        if variable.value is not None:
            # Handle empty string as valid value
            value_to_store = variable.value
            if variable_type == CREDENTIAL_TYPE:
                encrypted = auth_utils.encrypt_api_key(value_to_store, settings_service=self.settings_service)
                variable.value = encrypted

        variable_data = variable.model_dump(exclude_unset=True)
        for key, value in variable_data.items():
            setattr(db_variable, key, value)

        session.add(db_variable)
        await session.flush()
        await session.refresh(db_variable)
        return db_variable

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

    async def delete_variable_by_id(self, user_id: UUID | str, variable_id: UUID, session: AsyncSession) -> None:
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.id == variable_id)
        variable = (await session.exec(stmt)).first()
        if not variable:
            msg = f"{variable_id} variable not found."
            raise ValueError(msg)
        await session.delete(variable)

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
        # Only encrypt CREDENTIAL_TYPE variables
        encrypted_value = (
            auth_utils.encrypt_api_key(value, settings_service=self.settings_service)
            if type_ == CREDENTIAL_TYPE
            else value
        )
        variable_base = VariableCreate(
            name=name,
            type=type_,
            value=encrypted_value,
            default_fields=list(default_fields),
        )
        variable = Variable.model_validate(variable_base, from_attributes=True, update={"user_id": user_id})
        session.add(variable)
        await session.flush()
        await session.refresh(variable)
        return variable
