"""Client creation, authentication, and credential resolution for the Watsonx Orchestrate adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient
from ibm_watsonx_orchestrate_clients.connections.connections_client import ConnectionsClient
from ibm_watsonx_orchestrate_clients.tools.tool_client import ToolClient
from lfx.services.adapters.deployment.exceptions import AuthSchemeError, CredentialResolutionError
from lfx.services.adapters.deployment.schema import EnvVarSource, EnvVarValueSpec, IdLike

from langflow.services.adapters.deployment.context import get_current_deployment_provider_id
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import WxOAuthURL
from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient, WxOCredentials
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.deployment_provider_account.crud import get_provider_account_by_id
from langflow.services.deps import get_variable_service

if TYPE_CHECKING:
    from uuid import UUID

    from ibm_cloud_sdk_core.authenticators import Authenticator
    from ibm_watsonx_orchestrate_core.types.connections import KeyValueConnectionCredentials


def get_authenticator(instance_url: str, api_key: str) -> Authenticator:
    """Return the appropriate authenticator for the Watsonx Orchestrate API."""
    if ".cloud.ibm.com" in instance_url:
        from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

        return IAMAuthenticator(apikey=api_key, url=WxOAuthURL.IBM_IAM.value)
    elif ".ibm.com" in instance_url:  # noqa: RET505 - explicitness
        from ibm_cloud_sdk_core.authenticators import MCSPAuthenticator

        return MCSPAuthenticator(apikey=api_key, url=WxOAuthURL.MCSP.value)

    msg = f"Could not determine authentication scheme for instance URL: {instance_url}"
    raise AuthSchemeError(message=msg)


def get_current_provider_id() -> UUID:
    provider_id = get_current_deployment_provider_id()
    if provider_id is None:
        msg = "Deployment account context is not available for adapter resolution."
        raise CredentialResolutionError(message=msg)
    return provider_id


async def resolve_wxo_client_credentials(
    *,
    user_id: UUID | str,
    db: Any,
    provider_id: UUID,
) -> WxOCredentials:
    """Resolve Watsonx Orchestrate client credentials from deployment provider account."""
    try:
        provider_account = await get_provider_account_by_id(
            db,
            provider_id=provider_id,
            user_id=user_id,
        )
        if provider_account is None:
            msg = "Failed to find deployment provider account credentials."
            raise CredentialResolutionError(message=msg)

        instance_url = (provider_account.backend_url or "").strip()
        api_key = auth_utils.decrypt_api_key((provider_account.api_key or "").strip())
        if not instance_url or not api_key:
            msg = "Watsonx Orchestrate backend URL and API key must be configured."
            raise CredentialResolutionError(message=msg)

    # please ensure that when raising or re-raising an exception,
    # that the message does not leak sensitive information
    except CredentialResolutionError:  # custom exception managed by us, so we re-raise
        raise
    except Exception:  # noqa: BLE001
        msg = "An unexpected error occurred while resolving Watsonx Orchestrate client credentials."
        raise CredentialResolutionError(message=msg) from None

    return WxOCredentials(instance_url=instance_url, api_key=api_key)


async def get_provider_clients(
    *,
    user_id: UUID | str,
    db: Any,
    client_cache: dict[str, WxOClient],
) -> WxOClient:
    provider_id = get_current_provider_id()
    cache_key = str(provider_id)
    if cache_key in client_cache:
        return client_cache[cache_key]

    credentials: WxOCredentials = await resolve_wxo_client_credentials(
        user_id=user_id,
        db=db,
        provider_id=provider_id,
    )

    instance_url: str = credentials.instance_url.rstrip("/")

    authenticator: Authenticator = get_authenticator(
        instance_url=instance_url,
        api_key=credentials.api_key,
    )

    client_cache[cache_key] = WxOClient(
        instance_url=instance_url,
        authenticator=authenticator,
        tool=ToolClient(base_url=instance_url, authenticator=authenticator),
        connections=ConnectionsClient(base_url=instance_url, authenticator=authenticator),
        agent=AgentClient(base_url=instance_url, authenticator=authenticator),
    )

    return client_cache[cache_key]


async def resolve_runtime_credentials(
    *,
    user_id: IdLike,
    environment_variables: dict[str, EnvVarValueSpec],
    db: Any,
) -> KeyValueConnectionCredentials:
    """Resolve runtime credentials from environment variables."""
    from ibm_watsonx_orchestrate_core.types.connections import KeyValueConnectionCredentials

    resolved: dict[str, str] = {}
    for credential_key, env_var_value in environment_variables.items():
        resolved[credential_key] = await resolve_env_var_value(
            env_var_value,
            user_id=user_id,
            db=db,
        )
    return KeyValueConnectionCredentials(resolved)


async def resolve_env_var_value(
    env_var_value: EnvVarValueSpec,
    *,
    user_id: IdLike,
    db: Any,
) -> str:
    if env_var_value.source == EnvVarSource.RAW:
        return env_var_value.value
    return await resolve_variable_value(
        env_var_value.value,
        user_id=user_id,
        db=db,
    )


async def resolve_variable_value(
    variable_name: str,
    *,
    user_id: UUID | str,
    db: Any,
    optional: bool = False,
    default_value: str | None = None,
) -> str:
    variable_service = get_variable_service()
    if variable_service is None:
        msg = "Variable service is not available."
        raise ValueError(msg)
    try:
        value = await variable_service.get_variable(
            user_id=user_id,
            name=variable_name,
            field="value",
            session=db,
        )
        if value is not None:
            return value
    except Exception:
        if not optional:
            raise
    if optional:
        return default_value or ""
    msg = (
        "Failed to find a necessary credential for the "
        "watsonX Orchestrate deployment provider. "
        "Please ensure all credentials are provided and valid."
    )
    raise CredentialResolutionError(message=msg)
