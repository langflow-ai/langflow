"""Database-backed connection persistence and runtime resolution."""

from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from lfx.integrations.capabilities import ScopeSet
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    ConnectionUnresolvedError,
    IntegrationError,
    ScopeMissingError,
)
from lfx.integrations.models import (
    ConnectionRef,
    ConnectionResolutionRequest,
    ConnectionStatus,
    ResolvedCredential,
)
from lfx.log.logger import logger
from lfx.services.connection.base import BaseConnectionResolverService, ConnectionAccessPolicy
from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlmodel import and_, col, false, or_, select

from langflow.services.auth import utils as auth_utils
from langflow.services.authorization import filter_visible_resources, visible_scope_prefilter
from langflow.services.authorization.listing import (
    apply_owned_or_visible_scope_prefilter,
    restrict_to_owned_or_visible_scope,
)
from langflow.services.connection.oauth import broker
from langflow.services.connection.oauth.config import OAuthError
from langflow.services.connection.oauth.locking import lock_connection
from langflow.services.database.models.connection import (
    Connection,
    ConnectionCreate,
    ConnectionHealth,
    ConnectionOwnershipMode,
    ConnectionRead,
    ConnectionSecret,
    ConnectionStatusReason,
    ConnectionUpdate,
    ExecutingIdentityDescriptor,
    PersistedConnectionStatus,
)
from langflow.services.database.models.connection.schemas import ConnectionRevokeRead
from langflow.services.deps import get_authorization_service, get_settings_service, session_scope

if TYPE_CHECKING:
    from lfx.services.authorization.base import ExecutionPrincipal
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead


# Route families whose dependency principal is ``actor_or_explicit_share``
# (connection-contract.md section 4). scripts/ci/check_execution_principal_matrix.py
# fails when this set and scripts/ci/execution_principal_matrix.json disagree.
# Every other family resolves owner or instance connections only.
_SHARE_PERMITTING_FAMILIES = frozenset({"interactive_chat", "v1_run", "openai_responses", "voice", "workflow_v2"})

# Upper bound on foreign rows one share lookup loads and authorizes. Handles are
# owner-neutral, so without it a plugin that cannot prefilter by visibility
# would make every resolution scan every user's connection with that handle.
# Past the bound, resolution fails closed like any other ambiguous share.
_MAX_SHARE_CANDIDATES = 50

# Statuses in which a connection deliberately holds no credential, so a missing
# envelope is expected rather than an error.
_CREDENTIAL_FREE_STATUSES = frozenset(
    {PersistedConnectionStatus.PENDING.value, PersistedConnectionStatus.REVOKED.value}
)


async def _audit_resolution_denial(
    request: ConnectionResolutionRequest,
    *,
    row: Connection | None,
    error: IntegrationError,
) -> None:
    """Record a refused connection resolution, best effort.

    Resolution happens deep inside a graph run -- often on a worker with no
    request -- so this must never turn a denial into a crash. ``audit_decision``
    is a no-op unless ``AUTHZ_AUDIT_ENABLED``. ``details.resource`` says
    ``integration_connection`` because ``connection`` already names an
    SSO/directory connection in the Enterprise audit projection.
    """
    if not isinstance(error, ConnectionNotAuthorizedError):
        return
    try:
        from langflow.services.authorization.audit import audit_decision

        user_id = None
        if request.principal.user_id is not None:
            with contextlib.suppress(ValueError):
                user_id = UUID(str(request.principal.user_id))
        await audit_decision(
            user_id=user_id,
            action="execute",
            obj=f"connection:{row.id}" if row is not None else f"connection:{request.ref.to_handle()}",
            result="deny",
            details={
                "resource": "integration_connection",
                "provider": request.ref.provider,
                "execution_family": request.principal.family,
                "execution_principal_kind": request.principal.kind,
                "interactive": request.principal.interactive,
            },
        )
    except Exception:  # noqa: BLE001 - audit must never break a resolution decision
        logger.debug("connection resolution denial audit failed", exc_info=True)


class ConnectionConflictError(ValueError):
    """Raised when an owner already has a connection with the same handle."""


class ConnectionSecretError(RuntimeError):
    """Raised when connection credential material cannot be encrypted or decoded."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _credential_payload(payload: ConnectionCreate) -> str | None:
    credentials = payload.credentials
    if credentials is None:
        return None
    return json.dumps(
        {
            "version": 1,
            "access_token": credentials.access_token.get_secret_value(),
            "refresh_token": (
                credentials.refresh_token.get_secret_value() if credentials.refresh_token is not None else None
            ),
            "token_type": credentials.token_type,
            "expires_at": credentials.expires_at.isoformat() if credentials.expires_at is not None else None,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _encrypt_credential_payload(payload: str) -> str:
    try:
        return auth_utils.encrypt_api_key(payload)
    except Exception as exc:
        msg = "Connection credential encryption failed; check the server encryption configuration"
        raise ConnectionSecretError(msg) from exc


def _decrypt_credential_payload(encrypted_payload: str) -> dict:
    try:
        plaintext = auth_utils.decrypt_api_key(encrypted_payload)
        if not plaintext:
            msg = "empty decrypted payload"
            raise ValueError(msg)
        decoded = json.loads(plaintext)
        if not isinstance(decoded, dict) or decoded.get("version") != 1:
            msg = "unsupported credential envelope"
            raise ValueError(msg)
        access_token = decoded.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            msg = "credential envelope has no access token"
            raise ValueError(msg)
        _parse_expiry(decoded.get("expires_at"))
    except Exception as exc:
        msg = "Stored connection credential could not be decoded"
        raise ConnectionSecretError(msg) from exc
    return decoded


def _parse_expiry(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        msg = "Stored connection credential has an invalid expiry"
        raise ConnectionSecretError(msg)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        msg = "Stored connection credential has an invalid expiry"
        raise ConnectionSecretError(msg) from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _set_status(
    row: Connection,
    status: PersistedConnectionStatus,
    reason: ConnectionStatusReason | None = None,
) -> None:
    row.status = status.value
    row.status_reason = reason.value if reason is not None else None


def _principal_user_id(principal: ExecutionPrincipal) -> UUID | None:
    if principal.user_id is None:
        return None
    try:
        return UUID(str(principal.user_id))
    except ValueError:
        return None


def _access_policy(row: Connection, *, explicit_share_authorized: bool) -> ConnectionAccessPolicy:
    return ConnectionAccessPolicy(
        owner_kind=row.ownership_mode,
        connection_owner_id=str(row.owner_id) if row.owner_id is not None else None,
        connection_id=str(row.id),
        allow_non_interactive=bool(row.allow_non_interactive),
        explicit_share_authorized=explicit_share_authorized,
    )


class DatabaseConnectionResolverService(BaseConnectionResolverService):
    """Resolve encrypted database connections while exposing only safe metadata."""

    def __init__(self) -> None:
        super().__init__()
        # Direct service-class registration does not call set_ready(), unlike
        # factory creation, and lfx's connection lookup rejects unready resolvers.
        self.set_ready()

    async def create(
        self,
        session: AsyncSession,
        *,
        user: User | UserRead,
        payload: ConnectionCreate,
    ) -> ConnectionRead:
        owner_id = user.id if payload.ownership_mode == ConnectionOwnershipMode.USER else None
        now = _utc_now()
        raw_credentials = _credential_payload(payload)
        encrypted_payload = _encrypt_credential_payload(raw_credentials) if raw_credentials is not None else None
        row = Connection(
            owner_id=owner_id,
            ownership_mode=payload.ownership_mode.value,
            provider_key=payload.provider_key,
            name=payload.name,
            display_name=payload.display_name,
            status=(
                PersistedConnectionStatus.READY.value
                if encrypted_payload is not None
                else PersistedConnectionStatus.PENDING.value
            ),
            health=ConnectionHealth.UNKNOWN.value,
            granted_scopes=list(payload.granted_scopes),
            executing_identity=payload.executing_identity.model_dump(mode="json"),
            allow_non_interactive=payload.allow_non_interactive,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        try:
            await session.flush()
            if encrypted_payload is not None:
                session.add(ConnectionSecret(connection_id=row.id, encrypted_payload=encrypted_payload))
                await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            msg = "A connection with this provider and name already exists"
            raise ConnectionConflictError(msg) from exc
        await session.refresh(row)
        return self.to_read(row, has_credentials=encrypted_payload is not None)

    async def list_for_user(
        self,
        session: AsyncSession,
        *,
        user: User | UserRead,
        provider_key: str | None = None,
    ) -> list[ConnectionRead]:
        is_superuser = bool(getattr(user, "is_superuser", False))
        owner_clause = or_(
            Connection.owner_id == user.id,
            Connection.ownership_mode == ConnectionOwnershipMode.INSTANCE.value,
        )
        stmt = select(Connection)
        if provider_key is not None:
            stmt = stmt.where(Connection.provider_key == provider_key)
        authz = get_authorization_service()
        cross_user = await authz.is_enabled() and await authz.supports_cross_user_fetch()
        if not is_superuser:
            if cross_user:
                visibility = await visible_scope_prefilter(user, resource_type="connection", act="read")
                if visibility is not None:
                    stmt = await apply_owned_or_visible_scope_prefilter(
                        stmt,
                        id_column=Connection.id,
                        owner_clause=owner_clause,
                        visibility=visibility,
                    )
            else:
                stmt = stmt.where(owner_clause)
        stmt = stmt.order_by(col(Connection.display_name), col(Connection.id))
        rows = list((await session.exec(stmt)).all())
        if not is_superuser and cross_user:
            rows = await filter_visible_resources(
                user,
                resource_type="connection",
                candidates=rows,
                owner_extractor=lambda item: user.id
                if item.ownership_mode == ConnectionOwnershipMode.INSTANCE.value
                else item.owner_id,
                act="read",
            )
        secret_ids = (
            set(
                (
                    await session.exec(
                        select(ConnectionSecret.connection_id).where(
                            col(ConnectionSecret.connection_id).in_([row.id for row in rows])
                        )
                    )
                ).all()
            )
            if rows
            else set()
        )
        return [self.to_read(row, has_credentials=row.id in secret_ids) for row in rows]

    async def get_for_user(
        self,
        session: AsyncSession,
        *,
        user: User | UserRead,
        connection_id: UUID,
        for_update: bool = False,
    ) -> Connection | None:
        if for_update:
            # The lock is taken before the owner filter below, so callers must
            # authorize the row in a separate read first (see the connections
            # API's _authorized_row); this lookup then repeats under the lock.
            await lock_connection(session, connection_id)
        authz = get_authorization_service()
        may_fetch_cross_user = bool(getattr(user, "is_superuser", False)) or (
            await authz.is_enabled() and await authz.supports_cross_user_fetch()
        )
        stmt = select(Connection).where(Connection.id == connection_id)
        if not may_fetch_cross_user:
            stmt = stmt.where(
                or_(
                    Connection.owner_id == user.id,
                    Connection.ownership_mode == ConnectionOwnershipMode.INSTANCE.value,
                )
            )
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await session.exec(stmt)).first()

    async def has_credentials(self, session: AsyncSession, connection_id: UUID) -> bool:
        return await session.get(ConnectionSecret, connection_id) is not None

    async def revoke(self, session: AsyncSession, row: Connection) -> ConnectionRevokeRead:
        provider_revocation = await broker.revoke(session, row)
        secret = await session.get(ConnectionSecret, row.id)
        if secret is not None:
            await session.delete(secret)
        _set_status(row, PersistedConnectionStatus.REVOKED)
        row.health = ConnectionHealth.UNHEALTHY.value
        row.health_checked_at = _utc_now()
        row.updated_at = row.health_checked_at
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return ConnectionRevokeRead(
            **self.to_read(row, has_credentials=False).model_dump(), provider_revocation=provider_revocation
        )

    async def update(self, session: AsyncSession, row: Connection, payload: ConnectionUpdate) -> ConnectionRead:
        """Apply owner-editable metadata; the stored credential is untouched."""
        if payload.display_name is not None:
            row.display_name = payload.display_name
        if payload.allow_non_interactive is not None:
            row.allow_non_interactive = payload.allow_non_interactive
        row.updated_at = _utc_now()
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return self.to_read(row, has_credentials=await self.has_credentials(session, row.id))

    async def delete(self, session: AsyncSession, row: Connection) -> None:
        await self.revoke(session, row)
        await session.delete(row)
        await session.flush()

    async def check_health(
        self,
        session: AsyncSession,
        *,
        row: Connection,
        principal: ExecutionPrincipal,
        required_scopes: frozenset[str] = frozenset(),
    ) -> ConnectionRead:
        try:
            await self._check_row_credential(session, row=row, principal=principal, required_scopes=required_scopes)
        except AuthExpiredError:
            _set_status(row, PersistedConnectionStatus.EXPIRED)
            row.health = ConnectionHealth.UNHEALTHY.value
        except ConnectionUnresolvedError as exc:
            # The stored credential is unusable. Pending and revoked rows hold
            # none by design; any other row is in error, with the cause recorded
            # so a key change does not read as N unrelated user problems.
            if exc.reason == "credential-undecryptable":
                _set_status(row, PersistedConnectionStatus.ERROR, ConnectionStatusReason.CREDENTIAL_UNDECRYPTABLE)
            elif row.status not in _CREDENTIAL_FREE_STATUSES:
                _set_status(row, PersistedConnectionStatus.ERROR, ConnectionStatusReason.CREDENTIAL_MISSING)
            row.health = ConnectionHealth.UNHEALTHY.value
        except IntegrationError:
            # Scope coverage and principal denials describe this request, not
            # the stored credential, so the connection's status stands.
            row.health = ConnectionHealth.UNHEALTHY.value
        else:
            _set_status(row, PersistedConnectionStatus.READY)
            row.health = ConnectionHealth.HEALTHY.value
        row.health_checked_at = _utc_now()
        row.updated_at = row.health_checked_at
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return self.to_read(row, has_credentials=await self.has_credentials(session, row.id))

    async def _get_access_policy(self, request: ConnectionResolutionRequest) -> ConnectionAccessPolicy:
        user_id = _principal_user_id(request.principal)
        async with session_scope() as session:
            row = await self._owned_or_instance_row(session, request.ref, user_id)
            explicit_share = row is None
            if explicit_share:
                row = await self._authorized_share(session, request, user_id)
        if row is None:
            raise ConnectionUnresolvedError(request.ref.to_handle(), provider=request.ref.provider)
        policy = _access_policy(row, explicit_share_authorized=explicit_share)
        await self._refuse_denied_policy(request, row=row, policy=policy)
        return policy

    async def _refuse_denied_policy(
        self,
        request: ConnectionResolutionRequest,
        *,
        row: Connection,
        policy: ConnectionAccessPolicy,
    ) -> None:
        """Raise, audited, when the floor or the instance hook refuses this row.

        The base class applies the same floor after this hook returns, but a host
        cannot observe that denial, so evaluating it here is what records it.
        """
        error = BaseConnectionResolverService.authorize_principal(
            self,
            request,
            connection_owner_id=policy.connection_owner_id,
            owner_kind=policy.owner_kind,
            allow_non_interactive=policy.allow_non_interactive,
            explicit_share_authorized=policy.explicit_share_authorized,
        )
        if error is None and row.ownership_mode == ConnectionOwnershipMode.INSTANCE.value:
            error = await self.authorize_instance_connection(request, row=row)
        if error is not None:
            await _audit_resolution_denial(request, row=row, error=error)
            raise error

    async def _resolve(
        self, request: ConnectionResolutionRequest, policy: ConnectionAccessPolicy
    ) -> ResolvedCredential:
        if policy.connection_id is None:
            raise ConnectionUnresolvedError(request.ref.to_handle(), provider=request.ref.provider)
        # _get_access_policy's read transaction has already ended, so the write
        # lock is the first statement of a fresh transaction.
        async with session_scope() as session:
            row = await lock_connection(session, UUID(policy.connection_id))
            if row is None or (row.provider_key, row.name) != (request.ref.provider, request.ref.name):
                raise ConnectionUnresolvedError(request.ref.to_handle(), provider=request.ref.provider)
            # Fail closed if ownership or the non-interactive opt-in changed
            # after the base class authorized the policy.
            drifted = _access_policy(row, explicit_share_authorized=policy.explicit_share_authorized) != policy
            resolution_error = None
            if not drifted:
                try:
                    credential = await self._credential_from_row(
                        session, row=row, rejected_token_digest=request.rejected_token_digest
                    )
                except IntegrationError as exc:
                    # A rotating refresh token may already have been exchanged. Keep
                    # that encrypted update; the base class checks scopes only after
                    # this transaction commits, so narrowed scopes keep it as well.
                    resolution_error = exc
        if drifted:
            # Audited once the row lock is released: a durable audit write would
            # otherwise wait on this transaction under SQLite.
            denial = ConnectionNotAuthorizedError(provider=request.ref.provider)
            await _audit_resolution_denial(request, row=row, error=denial)
            raise denial
        if resolution_error is not None:
            raise resolution_error
        return credential

    async def describe(self, ref: ConnectionRef, principal: ExecutionPrincipal) -> ConnectionStatus | None:
        request = ConnectionResolutionRequest(ref=ref, principal=principal)
        try:
            credential = await self.resolve(request)
        except AuthExpiredError:
            return ConnectionStatus(ref=ref, status="expired")
        except ScopeMissingError:
            return ConnectionStatus(ref=ref, status="scope_missing")
        except ConnectionUnresolvedError as exc:
            # An undecryptable credential is configured; "missing" would send
            # the builder to configure it again instead of reconnecting.
            return ConnectionStatus(ref=ref, status="missing" if exc.reason == "missing" else "unavailable")
        except IntegrationError:
            return ConnectionStatus(ref=ref, status="unavailable")
        return ConnectionStatus(
            ref=ref,
            status="ready",
            granted_scopes=credential.granted_scopes,
            account=credential.account,
        )

    @staticmethod
    async def _owned_or_instance_row(
        session: AsyncSession,
        ref: ConnectionRef,
        user_id: UUID | None,
    ) -> Connection | None:
        """Return the caller's row for a handle, else the instance row.

        The partial unique indexes allow at most one of each, so this never
        loads another user's rows. An owned record shadows the instance
        fallback: if its policy denies this principal, the base class's portable
        floor raises instead of silently switching identities to an instance
        credential with the same handle.
        """
        ownership = Connection.ownership_mode == ConnectionOwnershipMode.INSTANCE.value
        if user_id is not None:
            ownership = or_(
                and_(
                    Connection.ownership_mode == ConnectionOwnershipMode.USER.value,
                    Connection.owner_id == user_id,
                ),
                ownership,
            )
        rows = (
            await session.exec(
                select(Connection).where(
                    Connection.provider_key == ref.provider,
                    Connection.name == ref.name,
                    ownership,
                )
            )
        ).all()
        by_mode = {row.ownership_mode: row for row in rows}
        return by_mode.get(ConnectionOwnershipMode.USER.value) or by_mode.get(ConnectionOwnershipMode.INSTANCE.value)

    async def _authorized_share(
        self,
        session: AsyncSession,
        request: ConnectionResolutionRequest,
        user_id: UUID | None,
    ) -> Connection | None:
        """Return the one foreign row host authorization lets this actor execute."""
        principal = request.principal
        # Shares satisfy only an actor's owner mismatch, and only on route
        # families that permit shares; every other principal is owner-only.
        # Owner-only families (the legacy MCP transports) also clear
        # allow_explicit_shares: they never admit a delegated caller, so a share
        # must not be a wider grant through them than through its own route.
        if (
            principal.kind != "actor"
            or principal.family not in _SHARE_PERMITTING_FAMILIES
            or not principal.allow_explicit_shares
            or user_id is None
        ):
            return None
        settings = get_settings_service()
        authz = get_authorization_service()
        if not settings.auth_settings.AUTHZ_ENABLED or not await authz.supports_cross_user_fetch():
            return None
        context = {"execution_principal_kind": principal.kind}
        stmt = select(Connection).where(
            Connection.provider_key == request.ref.provider,
            Connection.name == request.ref.name,
            Connection.ownership_mode == ConnectionOwnershipMode.USER.value,
            Connection.owner_id != user_id,
        )
        if not principal.interactive:
            stmt = stmt.where(col(Connection.allow_non_interactive).is_(True))
        # Duck-typed services that predate the visibility hook fall back to the
        # capped scan below, as list endpoints do.
        get_visibility = getattr(authz, "get_resource_visibility", None)
        visibility = (
            await get_visibility(user_id=user_id, resource_type="connection", act="execute", context=context)
            if get_visibility is not None
            else None
        )
        if visibility is not None:
            if not visibility.has_cross_user_access:
                return None
            stmt = restrict_to_owned_or_visible_scope(
                stmt, id_column=Connection.id, owner_clause=false(), visibility=visibility
            )
        shared = list((await session.exec(stmt.order_by(col(Connection.id)).limit(_MAX_SHARE_CANDIDATES + 1))).all())
        if not shared:
            return None
        if len(shared) > _MAX_SHARE_CANDIDATES:
            logger.warning(
                "Not resolving shared connection %s: more than %d candidate rows share the handle",
                request.ref.to_handle(),
                _MAX_SHARE_CANDIDATES,
            )
            return None
        decisions = await authz.batch_enforce(
            user_id=user_id,
            domain="*",
            requests=[(f"connection:{row.id}", "execute") for row in shared],
            context=context,
        )
        authorized = [row for row, allowed in zip(shared, decisions, strict=True) if allowed]
        # A handle is intentionally owner-neutral. More than one shared match is
        # ambiguous, so fail closed instead of selecting credential material by
        # incidental database order.
        return authorized[0] if len(authorized) == 1 else None

    async def authorize_instance_connection(
        self,
        request: ConnectionResolutionRequest,
        *,
        row: Connection,
    ) -> IntegrationError | None:
        """Decide whether this principal may reference an INSTANCE-owned connection.

        The 1.13 default is the portable floor and nothing more: any principal
        except ``anonymous_public``/``unknown`` (already refused upstream) may
        resolve an instance row. Recorded in
        ``design/dedicated-integrations/decisions/instance-connection-referenceability.md``.

        This is the seam an integration-policy service (INT-7) overrides to
        narrow referenceability -- an approved-provider ceiling, a per-tenant
        allowlist, or a ``referenceable`` flag. Returning an ``IntegrationError``
        denies; returning ``None`` allows.
        """
        _ = (request, row)
        return None

    async def _check_row_credential(
        self,
        session: AsyncSession,
        *,
        row: Connection,
        principal: ExecutionPrincipal,
        required_scopes: frozenset[str],
    ) -> ResolvedCredential:
        """Validate one route-authorized row through the same floor and scope checks as ``resolve``.

        ``resolve`` selects by owner-neutral handle, so a health check of a
        specific row cannot go through it. The connections route has already
        authorized ``connection:execute`` for this row, which is the host share
        decision; the portable floor still applies to every other denial.
        """
        request = ConnectionResolutionRequest(
            ref=ConnectionRef(provider=row.provider_key, name=row.name),
            principal=principal,
            required_scopes=required_scopes,
        )
        is_foreign_user_row = (
            row.ownership_mode == ConnectionOwnershipMode.USER.value
            and str(row.owner_id) != str(principal.user_id)
            # Owner-only families never widen the floor for a share, even when
            # the host authorization service would have approved one.
            and principal.allow_explicit_shares
        )
        policy = _access_policy(row, explicit_share_authorized=is_foreign_user_row)
        denial = BaseConnectionResolverService.authorize_principal(
            self,
            request,
            connection_owner_id=policy.connection_owner_id,
            owner_kind=policy.owner_kind,
            allow_non_interactive=policy.allow_non_interactive,
            explicit_share_authorized=policy.explicit_share_authorized,
        )
        if denial is not None:
            await _audit_resolution_denial(request, row=row, error=denial)
            raise denial
        credential = await self._credential_from_row(session, row=row)
        missing = ScopeSet.missing(
            provider=row.provider_key, required=required_scopes, granted=credential.granted_scopes
        )
        if missing:
            raise ScopeMissingError(frozenset(missing), provider=row.provider_key)
        return credential

    async def _credential_from_row(
        self, session: AsyncSession, *, row: Connection, rejected_token_digest: str | None = None
    ) -> ResolvedCredential:
        handle = ConnectionRef(provider=row.provider_key, name=row.name).to_handle()
        if row.status == PersistedConnectionStatus.REVOKED.value:
            raise ConnectionUnresolvedError(handle, provider=row.provider_key)
        secret = await session.get(ConnectionSecret, row.id)
        if secret is None:
            raise ConnectionUnresolvedError(handle, provider=row.provider_key)
        try:
            payload = _decrypt_credential_payload(secret.encrypted_payload)
        except ConnectionSecretError:
            payload = None
        if payload is None:
            # Raised outside the handler so neither the decryption failure nor
            # any decrypted plaintext stays reachable from the public error.
            logger.warning(
                "Stored credential for connection %s could not be decrypted; "
                "if many connections report this, the server secret key may have changed",
                row.id,
            )
            raise ConnectionUnresolvedError(handle, provider=row.provider_key, reason="credential-undecryptable")
        try:
            payload = await broker.refresh_if_needed(session, row, payload, rejected_token_digest=rejected_token_digest)
        except OAuthError:
            raise AuthExpiredError(provider=row.provider_key) from None
        expires_at = _parse_expiry(payload.get("expires_at"))
        if expires_at is not None and expires_at <= _utc_now():
            raise AuthExpiredError(provider=row.provider_key)
        granted = frozenset(row.granted_scopes)
        identity = ExecutingIdentityDescriptor.model_validate(row.executing_identity)
        return ResolvedCredential(
            access_token=SecretStr(payload["access_token"]),
            token_type=str(payload.get("token_type") or "Bearer"),
            expires_at=expires_at,
            granted_scopes=granted,
            scopes_verified=True,
            account=identity.account,
            connection_id=str(row.id),
            owner_kind=row.ownership_mode,
            provider=row.provider_key,
            name=row.name,
        )

    @staticmethod
    def to_read(row: Connection, *, has_credentials: bool) -> ConnectionRead:
        return ConnectionRead.model_validate(
            {
                **row.model_dump(),
                # A reason explains only the error status, so a writer that
                # restores another status cannot leave a stale cause visible.
                "status_reason": row.status_reason if row.status == PersistedConnectionStatus.ERROR.value else None,
                "has_credentials": has_credentials,
            }
        )
