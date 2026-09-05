"""Environment-backed connection resolution for a host without Langflow's database.

``EnvConnectionResolver`` ships with LFX and is the resolver every headless
runtime gets when no other one is configured, so an environment-backed host
implements nothing: it only decides *how* the credential reaches the process.

Two injection channels exist, and the request-scoped one always wins:

1. Process environment. ``LF_CONNECTION__<PROVIDER>__<NAME>`` holds either a bare
   access token or a credential JSON object.
2. Request scope. The host binds a per-request map before executing the graph, so
   one caller's credential never becomes another caller's ambient default.
   ``lfx serve`` does this for you from the request body's ``global_vars``.

Both forms are validated by the same wire-format rules: an access token is
required, long-lived secrets (``refresh_token``, ``client_secret``, ``password``)
are rejected outright, and unknown fields are refused.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.integrations import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.env_resolver import EnvConnectionResolver
from lfx.services.variable.request_scope import (
    activate_request_variables,
    reset_request_variables,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from lfx.integrations import ResolvedCredential


def env_key_for(handle: str) -> str:
    """Return the environment/request-scope key a connection handle resolves from.

    Provider punctuation is hex-escaped so ``a.b``, ``a-b`` and ``a_b`` stay distinct:
    ``test.provider/work`` becomes ``LF_CONNECTION__TEST_2EPROVIDER__WORK``.
    """
    return ConnectionRef.parse(handle).env_key()


def credential_json(
    access_token: str,
    *,
    expires_at: datetime | None = None,
    scopes: Iterable[str] = (),
    account_id: str | None = None,
) -> str:
    """Build the JSON wire value for one connection.

    Use the JSON form when the injector knows the expiry, the granted scopes, or
    the account: LFX then fails with ``auth-expired`` before the call instead of
    after the provider rejects it, and with ``scope-missing`` when the action needs
    a scope the credential was not granted. A bare token string is the short form
    of ``{"access_token": "..."}`` with nothing else asserted.
    """
    payload: dict[str, Any] = {"access_token": access_token}
    if expires_at is not None:
        payload["expires_at"] = expires_at.astimezone(timezone.utc).isoformat()
    scope_list = sorted(scopes)
    if scope_list:
        payload["scopes"] = scope_list
    if account_id is not None:
        payload["account"] = {"id": account_id}
    # Deliberately absent: refresh_token, client_secret, password. Refresh is the
    # injector's job; a headless runtime only ever receives a short-lived token.
    return json.dumps(payload)


def _request(handle: str, required_scopes: Iterable[str]) -> ConnectionResolutionRequest:
    # ``headless_operator`` is the only principal kind allowed to use an
    # environment-owned connection. lfx run and lfx serve stamp it on the graph
    # for you (lfx.run._defaults.apply_run_defaults); a host driving the resolver
    # directly builds the same principal here.
    return ConnectionResolutionRequest(
        ref=ConnectionRef.parse(handle),
        principal=ExecutionPrincipal(kind="headless_operator"),
        required_scopes=frozenset(required_scopes),
    )


async def resolve_from_process_environment(
    handle: str,
    *,
    required_scopes: Iterable[str] = (),
) -> ResolvedCredential:
    """Resolve one connection from ``os.environ``.

    Raises ``ConnectionUnresolvedError`` when the key is absent, ``AuthExpiredError``
    when the JSON form declares a past ``expires_at``, and ``ScopeMissingError`` when
    it declares ``scopes`` that do not cover *required_scopes*.
    """
    return await EnvConnectionResolver().resolve(_request(handle, required_scopes))


async def resolve_with_request_scope(
    handle: str,
    credentials: Mapping[str, str],
    *,
    required_scopes: Iterable[str] = (),
) -> ResolvedCredential:
    """Resolve one connection from a per-request map instead of the process environment.

    *credentials* is keyed by :func:`env_key_for`. Binding it for the duration of
    one request is what keeps a served worker from running a caller's flow on a
    credential that some earlier request left in the environment.
    """
    token = activate_request_variables(dict(credentials))
    try:
        return await EnvConnectionResolver().resolve(_request(handle, required_scopes))
    finally:
        reset_request_variables(token)
