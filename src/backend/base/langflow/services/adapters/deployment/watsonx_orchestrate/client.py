"""Client creation, authentication, and credential resolution for the Watsonx Orchestrate adapter.

This module uses request/execution-context memoization for provider clients:

- `get_provider_clients()` resolves provider context and prebuilt credentials/authenticator.
- The resulting `WxOClient` is memoized in a ContextVar for the active async execution context.
- Subsequent calls with the same `(provider_id, user_id)` in that context reuse the same
  `WxOClient` instance and skip repeated DB/decryption work.

Important behavior notes:
- Memoization is execution-context scoped (not cross-request/global state).
- The context stores a single `(key, client)` entry because deployment routing enforces one
  provider context per request path.
- If a different `(provider_id, user_id)` is requested in the same context, resolution fails.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ibm_cloud_sdk_core.authenticators import Authenticator, IAMAuthenticator, MCSPAuthenticator
from ibm_watsonx_orchestrate_core.types.connections import KeyValueConnectionCredentials
from lfx.services.adapters.deployment.exceptions import AuthSchemeError, CredentialResolutionError
from lfx.services.adapters.deployment.schema import EnvVarSource, EnvVarValueSpec, IdLike

from langflow.services.adapters.deployment.context import DeploymentProviderIDContext
from langflow.services.adapters.deployment.watsonx_orchestrate.constants import WxOAuthURL
from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient, WxOCredentials
from langflow.services.auth import utils as auth_utils
from langflow.services.database.models.deployment_provider_account.crud import get_provider_account_by_id
from langflow.services.deps import get_variable_service

if TYPE_CHECKING:
    from contextvars import Token
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class WxOProviderClientsContext:
    provider_id: str
    user_id: str
    clients: WxOClient


class WxOProviderClientsRequestContext:
    _current: ClassVar[ContextVar[WxOProviderClientsContext | None]] = ContextVar(
        "langflow_wxo_provider_clients_request_context",
        default=None,
    )

    @classmethod
    def get_current(cls) -> WxOProviderClientsContext | None:
        return cls._current.get()

    @classmethod
    def set_current(cls, context: WxOProviderClientsContext) -> Token[WxOProviderClientsContext | None]:
        return cls._current.set(context)

    @classmethod
    def reset_current(cls, token: Token[WxOProviderClientsContext | None]) -> None:
        cls._current.reset(token)

    @classmethod
    def clear_current(cls) -> None:
        cls._current.set(None)


def _provider_client_context_key(*, provider_id: UUID, user_id: UUID | str) -> tuple[str, str]:
    return (str(provider_id), str(user_id))


def clear_provider_clients_request_context() -> None:
    """Clear execution-context memoized provider clients for the current async context.

    This is mainly useful in tests and explicit context lifecycle control.
    """
    WxOProviderClientsRequestContext.clear_current()


def get_request_context_provider_clients(*, provider_id: UUID, user_id: UUID | str) -> WxOClient | None:
    """Return memoized provider clients for the active execution context, if present.

    Returns `None` when:
    - no provider clients have been memoized in this context yet, or
    - the memoized entry belongs to a different `(provider_id, user_id)` pair.
    """
    request_context = WxOProviderClientsRequestContext.get_current()
    if request_context is None:
        return None
    if (request_context.provider_id, request_context.user_id) == _provider_client_context_key(
        provider_id=provider_id,
        user_id=user_id,
    ):
        return request_context.clients
    return None


def _validate_request_context_provider_key(*, provider_id: UUID, user_id: UUID | str) -> None:
    request_context = WxOProviderClientsRequestContext.get_current()
    if request_context is None:
        return
    if (request_context.provider_id, request_context.user_id) != _provider_client_context_key(
        provider_id=provider_id,
        user_id=user_id,
    ):
        msg = (
            "A different deployment provider context was requested in the same execution context. "
            "This indicates an invalid mixed provider resolution flow."
        )
        raise CredentialResolutionError(message=msg)


def set_request_context_provider_clients(*, provider_id: UUID, user_id: UUID | str, clients: WxOClient) -> None:
    """Memoize provider clients for the active execution context."""
    _validate_request_context_provider_key(provider_id=provider_id, user_id=user_id)
    context = WxOProviderClientsContext(
        provider_id=str(provider_id),
        user_id=str(user_id),
        clients=clients,
    )
    WxOProviderClientsRequestContext.set_current(context)


def get_authenticator(instance_url: str, api_key: str) -> Authenticator:
    """Return the appropriate authenticator for the Watsonx Orchestrate API."""
    if ".cloud.ibm.com" in instance_url:
        return IAMAuthenticator(apikey=api_key, url=WxOAuthURL.IBM_IAM.value)
    elif ".ibm.com" in instance_url:  # noqa: RET505 - explicitness
        return MCSPAuthenticator(apikey=api_key, url=WxOAuthURL.MCSP.value)

    msg = f"Could not determine authentication scheme for instance URL: {instance_url}"
    raise AuthSchemeError(message=msg)


async def resolve_wxo_client_credentials(
    *,
    user_id: UUID | str,
    db: AsyncSession,
    provider_id: UUID,
) -> WxOCredentials:
    """Resolve Watsonx Orchestrate client credentials from deployment provider account.

    The decrypted API key is used only to instantiate the SDK authenticator and is not
    retained in adapter credential objects.
    """
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

    except CredentialResolutionError:
        raise
    except Exception as exc:
        msg = "An unexpected error occurred while resolving Watsonx Orchestrate client credentials."
        raise CredentialResolutionError(message=msg) from exc

    authenticator = get_authenticator(instance_url=instance_url, api_key=api_key)
    return WxOCredentials(instance_url=instance_url, authenticator=authenticator)


async def get_provider_clients(
    *,
    user_id: UUID | str,
    db: AsyncSession,
) -> WxOClient:
    """Resolve and return provider clients for the active deployment provider context.

    Fast-path: return execution-context memoized clients when `(provider_id, user_id)` matches.
    Slow-path: resolve credentials from DB, build authenticator, construct `WxOClient`, then memoize.
    """
    request_context = DeploymentProviderIDContext.get_current()
    if request_context is None:
        msg = "Deployment account context is not available for adapter resolution."
        raise CredentialResolutionError(message=msg)
    provider_id = request_context.provider_id
    _validate_request_context_provider_key(provider_id=provider_id, user_id=user_id)
    if context_clients := get_request_context_provider_clients(provider_id=provider_id, user_id=user_id):
        return context_clients

    credentials: WxOCredentials = await resolve_wxo_client_credentials(
        user_id=user_id,
        db=db,
        provider_id=provider_id,
    )

    clients = WxOClient(
        instance_url=credentials.instance_url,
        authenticator=credentials.authenticator,
    )
    set_request_context_provider_clients(provider_id=provider_id, user_id=user_id, clients=clients)
    return clients


async def resolve_runtime_credentials(
    *,
    user_id: IdLike,
    environment_variables: dict[str, EnvVarValueSpec],
    db: AsyncSession,
) -> KeyValueConnectionCredentials:
    """Resolve runtime credentials from environment variables."""
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
    db: AsyncSession,
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
    db: AsyncSession,
    optional: bool = False,
    default_value: str | None = None,
) -> str:
    variable_service = get_variable_service()
    if variable_service is None:
        msg = "Variable service is not available."
        raise CredentialResolutionError(message=msg)
    try:
        value = await variable_service.get_variable(
            user_id=user_id,
            name=variable_name,
            field="value",
            session=db,
        )
        if value is not None:
            return value
    except CredentialResolutionError:
        raise
    except Exception as exc:
        if not optional:
            msg = "Failed to resolve a credential variable for the watsonx Orchestrate deployment provider."
            raise CredentialResolutionError(message=msg) from exc
    if optional:
        return default_value or ""
    msg = (
        "Failed to find a necessary credential for the "
        "watsonx Orchestrate deployment provider. "
        "Please ensure all credentials are provided and valid."
    )
    raise CredentialResolutionError(message=msg)
