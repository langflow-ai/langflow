import os
from typing import Optional, Tuple, Union
from uuid import UUID

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable, VariableCreate
from langflow.services.settings.service import SettingsService
from langflow.services.variable.base import VariableService
from langflow.services.variable.kubernetes_secrets import KubernetesSecretManager, encode_user_id
from langflow.services.variable.service import CREDENTIAL_TYPE, GENERIC_TYPE
from loguru import logger
from sqlmodel import Session


class KubernetesSecretService(VariableService, Service):
    def __init__(self, settings_service: "SettingsService"):
        self.settings_service = settings_service
        # TODO: settings_service to set kubernetes namespace
        self.kubernetes_secrets = KubernetesSecretManager()

    def initialize_user_variables(self, user_id: Union[UUID, str], session: Session):
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
                self.kubernetes_secrets.create_secret(
                    name=secret_name,
                    data=variables,
                )
            except Exception as e:
                logger.error(f"Error creating {var} variable: {e}")

        else:
            logger.info("Skipping environment variable storage.")

    # resolve_variable is a helper function that resolves the variable name to the actual key in the secret
    def resolve_variable(
        self,
        secret_name: str,
        user_id: Union[UUID, str],
        name: str,
    ) -> Tuple[str, str]:
        variables = self.kubernetes_secrets.get_secret(name=secret_name)
        if not variables:
            raise ValueError(f"user_id {user_id} variable not found.")

        if name in variables:
            return name, variables[name]
        else:
            credential_name = CREDENTIAL_TYPE + "_" + name
            if credential_name in variables:
                return credential_name, variables[credential_name]
            else:
                raise ValueError(f"user_id {user_id} variable name {name} not found.")

    def get_variable(
        self,
        user_id: Union[UUID, str],
        name: str,
        field: str,
        _session: Session,
    ) -> str:
        secret_name = encode_user_id(user_id)
        key, value = self.resolve_variable(secret_name, user_id, name)
        if key.startswith(CREDENTIAL_TYPE + "_") and field == "session_id":  # type: ignore
            raise TypeError(
                f"variable {name} of type 'Credential' cannot be used in a Session ID field "
                "because its purpose is to prevent the exposure of values."
            )
        return value

    def list_variables(
        self,
        user_id: Union[UUID, str],
        _session: Session,
    ) -> list[Optional[str]]:
        variables = self.kubernetes_secrets.get_secret(name=encode_user_id(user_id))
        if not variables:
            return []

        names = []
        for key in variables.keys():
            if key.startswith(CREDENTIAL_TYPE + "_"):
                names.append(key[len(CREDENTIAL_TYPE) + 1 :])
            else:
                names.append(key)
        return names

    def update_variable(
        self,
        user_id: Union[UUID, str],
        name: str,
        value: str,
        _session: Session,
    ):
        secret_name = encode_user_id(user_id)
        secret_key, _ = self.resolve_variable(secret_name, user_id, name)
        return self.kubernetes_secrets.update_secret(name=secret_name, data={secret_key: value})

    def delete_variable(
        self,
        user_id: Union[UUID, str],
        name: str,
        _session: Session,
    ):
        secret_name = encode_user_id(user_id)
        secret_key, _ = self.resolve_variable(secret_name, user_id, name)
        self.kubernetes_secrets.delete_secret_key(name=secret_name, key=secret_key)
        return

    def create_variable(
        self,
        user_id: Union[UUID, str],
        name: str,
        value: str,
        default_fields: list[str],
        _type: str,
        _session: Session,
    ) -> Variable:
        secret_name = encode_user_id(user_id)
        secret_key = name
        if _type == CREDENTIAL_TYPE:
            secret_key = CREDENTIAL_TYPE + "_" + name
        else:
            _type = GENERIC_TYPE

        self.kubernetes_secrets.upsert_secret(secret_name=secret_name, data={secret_key: value})

        variable_base = VariableCreate(
            name=name,
            type=_type,
            value=auth_utils.encrypt_api_key(value, settings_service=self.settings_service),
            default_fields=default_fields,
        )
        variable = Variable.model_validate(variable_base, from_attributes=True, update={"user_id": user_id})
        return variable
