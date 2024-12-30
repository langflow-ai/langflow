from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from loguru import logger
from typing_extensions import override

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable, VariableCreate, VariableRead
from langflow.services.variable.base import VariableService
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from langflow.services.variable.kubernetes_secrets import KubernetesSecretManager, encode_user_id

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel import Session
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.settings.service import SettingsService


class KubernetesSecretService(VariableService, Service):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        # TODO: settings_service to set kubernetes namespace
        self.kubernetes_secrets = KubernetesSecretManager()

    @override
    async def initialize_user_variables(self, user_id: UUID | str, session: AsyncSession) -> None:
        # Check for environment variables that should be stored in the database
        should_or_should_not = "Should" if self.settings_service.settings.store_environment_variables else "Should not"
        logger.info(f"{should_or_should_not} store environment variables in the kubernetes.")
        if self.settings_service.settings.store_environment_variables:
            variables = {}
            for var in self.settings_service.settings.variables_to_get_from_environment:
                if var in os.environ:
                    logger.debug(f"Creating {var} variable from environment.")
                    value = os.environ[var]
                    if isinstance(value, str):
                        value = value.strip()
                    key = CREDENTIAL_TYPE + "_" + var
                    variables[key] = str(value)

            try:
                secret_name = encode_user_id(user_id)
                await asyncio.to_thread(
                    self.kubernetes_secrets.create_secret,
                    name=secret_name,
                    data=variables,
                )
            except Exception:  # noqa: BLE001
                logger.exception(f"Error creating {var} variable")

        else:
            logger.info("Skipping environment variable storage.")

    # resolve_variable is a helper function that resolves the variable name to the actual key in the secret
    def resolve_variable(
        self,
        secret_name: str,
        user_id: UUID | str,
        name: str,
    ) -> tuple[str, str]:
        variables = self.kubernetes_secrets.get_secret(name=secret_name)
        if not variables:
            msg = f"user_id {user_id} variable not found."
            raise ValueError(msg)

        if name in variables:
            return name, variables[name]
        credential_name = CREDENTIAL_TYPE + "_" + name
        if credential_name in variables:
            return credential_name, variables[credential_name]
        msg = f"user_id {user_id} variable name {name} not found."
        raise ValueError(msg)

    @override
    async def get_variable(self, user_id: UUID | str, name: str, field: str, session: AsyncSession) -> str:
        secret_name = encode_user_id(user_id)
        key, value = await asyncio.to_thread(self.resolve_variable, secret_name, user_id, name)
        if key.startswith(CREDENTIAL_TYPE + "_") and field == "session_id":
            msg = (
                f"variable {name} of type 'Credential' cannot be used in a Session ID field "
                "because its purpose is to prevent the exposure of values."
            )
            raise TypeError(msg)
        return value

    @override
    async def list_variables(
        self,
        user_id: UUID | str,
        session: Session,
    ) -> list[str | None]:
        variables = await asyncio.to_thread(self.kubernetes_secrets.get_secret, name=encode_user_id(user_id))
        if not variables:
            return []

        names = []
        for key in variables:
            if key.startswith(CREDENTIAL_TYPE + "_"):
                names.append(key[len(CREDENTIAL_TYPE) + 1 :])
            else:
                names.append(key)
        return names

    def _update_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
    ):
        secret_name = encode_user_id(user_id)
        secret_key, _ = self.resolve_variable(secret_name, user_id, name)
        return self.kubernetes_secrets.update_secret(name=secret_name, data={secret_key: value})

    @override
    async def update_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        session: AsyncSession,
    ):
        return await asyncio.to_thread(self._update_variable, user_id, name, value)

    def _delete_variable(self, user_id: UUID | str, name: str) -> None:
        secret_name = encode_user_id(user_id)
        secret_key, _ = self.resolve_variable(secret_name, user_id, name)
        self.kubernetes_secrets.delete_secret_key(name=secret_name, key=secret_key)

    @override
    async def delete_variable(self, user_id: UUID | str, name: str, session: AsyncSession) -> None:
        await asyncio.to_thread(self._delete_variable, user_id, name)

    @override
    async def delete_variable_by_id(self, user_id: UUID | str, variable_id: UUID | str, session: AsyncSession) -> None:
        await self.delete_variable(user_id, str(variable_id), session)

    @override
    async def create_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        *,
        default_fields: list[str],
        type_: str,
        session: AsyncSession,
    ) -> Variable:
        secret_name = encode_user_id(user_id)
        secret_key = name
        if type_ == CREDENTIAL_TYPE:
            secret_key = CREDENTIAL_TYPE + "_" + name
        else:
            type_ = GENERIC_TYPE

        await asyncio.to_thread(
            self.kubernetes_secrets.upsert_secret, secret_name=secret_name, data={secret_key: value}
        )

        variable_base = VariableCreate(
            name=name,
            type=type_,
            value=auth_utils.encrypt_api_key(value, settings_service=self.settings_service),
            default_fields=default_fields,
        )
        return Variable.model_validate(variable_base, from_attributes=True, update={"user_id": user_id})

    @override
    async def get_all(self, user_id: UUID | str, session: AsyncSession) -> list[VariableRead]:
        secret_name = encode_user_id(user_id)
        variables = await asyncio.to_thread(self.kubernetes_secrets.get_secret, name=secret_name)
        if not variables:
            return []

        variables_read = []
        for key, value in variables.items():
            name = key
            type_ = GENERIC_TYPE
            if key.startswith(CREDENTIAL_TYPE + "_"):
                name = key[len(CREDENTIAL_TYPE) + 1 :]
                type_ = CREDENTIAL_TYPE

            decrypted_value = None
            if type_ == GENERIC_TYPE:
                decrypted_value = value

            variable_base = VariableCreate(
                name=name,
                type=type_,
                value=auth_utils.encrypt_api_key(value, settings_service=self.settings_service),
                default_fields=[],
            )
            variable = Variable.model_validate(variable_base, from_attributes=True, update={"user_id": user_id})
            variable_read = VariableRead.model_validate(variable, from_attributes=True)
            variable_read.value = decrypted_value
            variables_read.append(variable_read)

        return variables_read
