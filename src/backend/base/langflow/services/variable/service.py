from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger
from sqlmodel import select

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable, VariableCreate, VariableRead, VariableUpdate
from langflow.services.variable.base import VariableService
from langflow.services.variable.constants import CATEGORY_GLOBAL, CREDENTIAL_TYPE, GENERIC_TYPE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.settings.service import SettingsService


class DatabaseVariableService(VariableService, Service):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    async def initialize_user_variables(self, user_id: UUID | str, session: AsyncSession) -> None:
        if not self.settings_service.settings.store_environment_variables:
            logger.info("Skipping environment variable storage.")
            return

        logger.info("Storing environment variables in the database.")
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
                            category=CATEGORY_GLOBAL,
                            session=session,
                        )
                    logger.info(f"Processed {var_name} variable from environment.")
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
        if isinstance(user_id, str):
            user_id = UUID(user_id)
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
        if isinstance(user_id, str):
            user_id = UUID(user_id)
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

    async def get_by_category(self, user_id: UUID | str, category: str, session: AsyncSession) -> list[VariableRead]:
        """Get all variables for a user by category."""
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.category == category)
        variables = list((await session.exec(stmt)).all())

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
        category: str | None = None,
    ):
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.name == name)
        variable = (await session.exec(stmt)).first()
        if not variable:
            msg = f"{name} variable not found."
            raise ValueError(msg)
        encrypted = auth_utils.encrypt_api_key(value, settings_service=self.settings_service)
        variable.value = encrypted

        # Update category if provided
        if category is not None:
            variable.category = category

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
        category: str = CATEGORY_GLOBAL,
        session: AsyncSession,
    ):
        variable_base = VariableCreate(
            name=name,
            type=type_,
            value=auth_utils.encrypt_api_key(value, settings_service=self.settings_service),
            default_fields=list(default_fields),
            category=category,
        )
        variable = Variable.model_validate(variable_base, from_attributes=True, update={"user_id": user_id})
        session.add(variable)
        await session.commit()
        await session.refresh(variable)
        return variable

    # Utility methods for LLM settings

    async def save_llm_settings(
        self,
        user_id: UUID | str,
        llm_settings: dict,
        session: AsyncSession,
    ) -> None:
        """Store LLM settings as variables under the LLM category.

        Args:
            user_id: The user ID
            llm_settings: Dictionary with LLM settings (provider, model, base_url, api_key)
            session: The database session
        """
        from langflow.services.variable.constants import CATEGORY_LLM

        # Store provider
        if "provider" in llm_settings:
            await self.create_or_update_variable(
                user_id=user_id,
                name="provider",
                value=llm_settings["provider"],
                type_=GENERIC_TYPE,
                category=CATEGORY_LLM,
                session=session,
            )

        # Store model
        if "model" in llm_settings:
            await self.create_or_update_variable(
                user_id=user_id,
                name="model",
                value=llm_settings["model"],
                type_=GENERIC_TYPE,
                category=CATEGORY_LLM,
                session=session,
            )

        # Store base_url
        if llm_settings.get("base_url"):
            await self.create_or_update_variable(
                user_id=user_id,
                name="base_url",
                value=llm_settings["base_url"],
                type_=GENERIC_TYPE,
                category=CATEGORY_LLM,
                session=session,
            )

        # Store API key (as credential)
        if llm_settings.get("api_key"):
            await self.create_or_update_variable(
                user_id=user_id,
                name="api_key",
                value=llm_settings["api_key"],
                type_=CREDENTIAL_TYPE,
                category=CATEGORY_LLM,
                session=session,
            )

    async def get_llm_settings(
        self,
        user_id: UUID | str,
        session: AsyncSession,
    ) -> dict:
        """Retrieve all LLM settings for a user.

        Args:
            user_id: The user ID
            session: The database session

        Returns:
            Dictionary with LLM settings
        """
        from langflow.services.variable.constants import CATEGORY_LLM

        # Get all variables in the LLM category
        variables = await self.get_by_category(user_id, CATEGORY_LLM, session)

        # Build settings dict
        settings_dict = {}
        for variable in variables:
            # For credentials, value will be None in VariableRead
            if variable.type == CREDENTIAL_TYPE:
                # Get the actual value using get_variable
                try:
                    value = await self.get_variable(user_id, variable.name, "value", session)
                    settings_dict[variable.name] = value
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error getting credential value for {variable.name}: {e}")
            else:
                # For non-credentials, value is already decrypted in get_by_category
                settings_dict[variable.name] = variable.value
        # We need at least provider, model, and api_key
        # This will be a user facing error so it has to be very clear
        required_fields = {"provider", "model", "api_key"}
        missing_fields = required_fields - set(settings_dict.keys())
        if missing_fields:
            msg = (
                "Please make sure to set the following LLM "
                f"settings: {[missing_field.capitalize() for missing_field in missing_fields]}"
            )
            raise ValueError(msg)

        return settings_dict

    async def create_or_update_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        type_: str,
        category: str,
        session: AsyncSession,
    ) -> Variable:
        """Create or update a variable.

        Args:
            user_id: The user ID
            name: The variable name
            value: The variable value
            type_: The variable type (CREDENTIAL_TYPE or GENERIC_TYPE)
            category: The variable category
            session: The database session

        Returns:
            The created or updated variable
        """
        # Check if variable exists
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.name == name, Variable.category == category)
        variable = (await session.exec(stmt)).first()

        if variable:
            # Update existing variable
            return await self.update_variable(
                user_id=user_id, name=name, value=value, session=session, category=category
            )
        # Create new variable
        return await self.create_variable(
            user_id=user_id,
            name=name,
            value=value,
            type_=type_,
            category=category,
            session=session,
        )
