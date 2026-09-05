"""A secret-manager connection resolver for a host without Langflow's database.

``SecretManagerConnectionResolver`` is the shape to copy when credentials live in
AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager, or any other store: the
resolver owns the lookup, and everything else — the deny floor, the wire format,
expiry, and scope verification — is reused from LFX so a host cannot accidentally
relax an invariant.

``MountedSecretsConnectionResolver`` is a working, dependency-free implementation
that reads a directory of secret files, the shape Kubernetes projected secrets and
Docker secrets already produce. Register it through ``lfx.toml``:

    [services]
    connection_resolver_service = "secret_manager_resolver:MountedSecretsConnectionResolver"

Registration fails closed. A class that does not subclass
``BaseConnectionResolverService``, or a module that cannot be imported, raises at
service resolution rather than silently falling back to the environment resolver.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from lfx.integrations import ConnectionUnresolvedError, ScopeMissingError
from lfx.integrations.errors import AuthExpiredError
from lfx.services.connection.base import BaseConnectionResolverService

# _parse_wire_value is internal to LFX today. Reusing it keeps this sample on the
# one wire format LFX validates — bare token or a JSON object whose only allowed
# fields are access_token, token_type, expires_at, scopes and account, and which
# refuses refresh_token, client_secret and password.
from lfx.services.connection.env_resolver import _parse_wire_value

if TYPE_CHECKING:
    from lfx.integrations import ConnectionRef, ConnectionResolutionRequest, ResolvedCredential

SecretFetcher = Callable[[str], str | None]

DEFAULT_SECRETS_DIR = "/run/secrets/langflow-connections"


class SecretManagerConnectionResolver(BaseConnectionResolverService):
    """Resolve connection handles from an external secret store.

    Subclass and override :meth:`fetch_secret`, or pass a callable to the
    constructor. The lookup runs on a worker thread, so a blocking vendor SDK
    client does not stall the event loop.
    """

    #: Secret name built from the connection handle. Handles are validated by
    #: ``ConnectionRef`` (``provider`` is ``[a-z0-9][a-z0-9._-]*``, ``name`` is
    #: ``[a-z0-9_]+``), so no separator in this template can be smuggled through.
    secret_name_template = "langflow/connections/{provider}/{name}"  # noqa: S105 - a store key, not a secret

    def __init__(self, fetch_secret: SecretFetcher | None = None) -> None:
        super().__init__()
        self._fetch_secret = fetch_secret
        # A resolver that is not ready fails closed in get_connection_resolver()
        # instead of degrading to the environment resolver, so preload whatever
        # your store needs (client, auth, cache) before calling set_ready().
        self.set_ready()

    def secret_name(self, ref: ConnectionRef) -> str:
        """Return the store key holding this connection's credential."""
        return self.secret_name_template.format(provider=ref.provider, name=ref.name)

    def fetch_secret(self, secret_name: str) -> str | None:
        """Return the raw secret value, or ``None`` when the store has no such secret."""
        if self._fetch_secret is None:
            msg = "Override fetch_secret() in a subclass or pass a fetch_secret callable"
            raise NotImplementedError(msg)
        return self._fetch_secret(secret_name)

    async def resolve(self, request: ConnectionResolutionRequest) -> ResolvedCredential:
        """Resolve a handle into a short-lived credential."""
        # The portable deny floor first: an environment/secret-store-owned
        # credential is usable only by a headless operator principal, never by an
        # interactive actor, an anonymous public run, or an unknown principal.
        denial = self.authorize_principal(
            request,
            connection_owner_id=None,
            owner_kind="env",
            allow_non_interactive=True,
        )
        if denial is not None:
            raise denial

        secret_name = self.secret_name(request.ref)
        raw = await asyncio.to_thread(self.fetch_secret, secret_name)
        if not raw:
            # No secret name and no store detail in the error: the message reaches
            # clients and telemetry. env_key is None because this host does not
            # resolve from the environment.
            raise ConnectionUnresolvedError(request.ref.to_handle(), provider=request.ref.provider)

        credential = _parse_wire_value(raw, request)
        if credential.expires_at is not None and credential.expires_at <= datetime.now(timezone.utc):
            raise AuthExpiredError(provider=request.ref.provider)
        if credential.scopes_verified:
            missing = request.required_scopes - credential.granted_scopes
            if missing:
                raise ScopeMissingError(frozenset(missing), provider=request.ref.provider)
        return credential


class MountedSecretsConnectionResolver(SecretManagerConnectionResolver):
    """Read credentials from a mounted secrets directory.

    One file per connection, named ``<provider>__<name>``, holding either a bare
    access token or the credential JSON object.
    """

    def __init__(self, secrets_dir: str | None = None) -> None:
        super().__init__()
        self._secrets_dir = Path(secrets_dir or DEFAULT_SECRETS_DIR)

    def secret_name(self, ref: ConnectionRef) -> str:
        """Return the file name holding this connection's credential."""
        return f"{ref.provider}__{ref.name}"

    def fetch_secret(self, secret_name: str) -> str | None:
        """Read one secret file, refusing any path that escapes the secrets directory."""
        root = self._secrets_dir.resolve()
        candidate = (root / secret_name).resolve()
        if not candidate.is_relative_to(root):
            msg = "Resolved secret path escapes the configured secrets directory"
            raise ValueError(msg)
        if not candidate.is_file():
            return None
        # Mounted secrets routinely carry a trailing newline from the writer.
        return candidate.read_text(encoding="utf-8").strip()


# Adapters for hosted secret stores follow the same shape. They are shown here
# rather than implemented so this sample keeps LFX's dependency set unchanged.
#
# AWS Secrets Manager:
#
#     import boto3
#
#     class AwsSecretsManagerResolver(SecretManagerConnectionResolver):
#         def __init__(self) -> None:
#             super().__init__()
#             self._client = boto3.client("secretsmanager")
#
#         def fetch_secret(self, secret_name: str) -> str | None:
#             try:
#                 return self._client.get_secret_value(SecretId=secret_name)["SecretString"]
#             except self._client.exceptions.ResourceNotFoundException:
#                 return None
#
# HashiCorp Vault (KV v2):
#
#     import hvac
#
#     class VaultResolver(SecretManagerConnectionResolver):
#         def __init__(self) -> None:
#             super().__init__()
#             self._client = hvac.Client()
#
#         def fetch_secret(self, secret_name: str) -> str | None:
#             read = self._client.secrets.kv.v2.read_secret_version(path=secret_name)
#             return read["data"]["data"].get("access_token")
#
# In both cases the store holds a short-lived access token that some other system
# refreshes. Do not put a refresh token or a client secret in it: _parse_wire_value
# rejects those fields, and a headless runtime has no consent context to use them.
