"""Database-backed connection persistence and runtime resolution."""

from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

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
from lfx.services.connection.base import BaseConnectionResolverService
from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, or_, select

from langflow.services.auth import utils as auth_utils
from langflow.services.authorization import filter_visible_resources, visible_scope_prefilter
from langflow.services.authorization.listing import apply_owned_or_visible_scope_prefilter
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
    ExecutingIdentityDescriptor,
    PersistedConnectionStatus,
)
from langflow.services.database.models.connection.schemas import ConnectionRevokeRead
from langflow.services.deps import get_authorization_service, get_settings_service, session_scope

if TYPE_CHECKING:
    from lfx.services.authorization.base import ExecutionPrincipal
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead


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


class DatabaseConnectionResolverService(BaseConnectionResolverService):
    """Resolve encrypted database connections while exposing only safe metadata."""

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
        row.status = PersistedConnectionStatus.REVOKED.value
        row.health = ConnectionHealth.UNHEALTHY.value
        row.health_checked_at = _utc_now()
        row.updated_at = row.health_checked_at
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return ConnectionRevokeRead(
            **self.to_read(row, has_credentials=False).model_dump(), provider_revocation=provider_revocation
        )

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
            await self._resolved_from_row(session, row=row, principal=principal, required_scopes=required_scopes)
        except AuthExpiredError:
            row.status = PersistedConnectionStatus.EXPIRED.value
            row.health = ConnectionHealth.UNHEALTHY.value
        except IntegrationError:
            row.health = ConnectionHealth.UNHEALTHY.value
        else:
            row.status = PersistedConnectionStatus.READY.value
            row.health = ConnectionHealth.HEALTHY.value
        row.health_checked_at = _utc_now()
        row.updated_at = row.health_checked_at
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return self.to_read(row, has_credentials=await self.has_credentials(session, row.id))

    async def resolve(self, request: ConnectionResolutionRequest) -> ResolvedCredential:
        async with session_scope() as session:
            candidates = list(
                (
                    await session.exec(
                        select(Connection)
                        .where(
                            Connection.provider_key == request.ref.provider,
                            Connection.name == request.ref.name,
                        )
                        .order_by(col(Connection.id))
                    )
                ).all()
            )
            row = await self._select_authorized_candidate(candidates, request)
            if row is None:
                raise ConnectionUnresolvedError(request.ref.to_handle(), provider=request.ref.provider)
            connection_id = row.id
        # End discovery's read transaction before acquiring the write lock.
        async with session_scope() as session:
            row = await lock_connection(session, connection_id)
            if row is None:
                raise ConnectionUnresolvedError(request.ref.to_handle(), provider=request.ref.provider)
            authorized = await self._select_authorized_candidate([row], request)
            if authorized is None:
                raise ConnectionUnresolvedError(request.ref.to_handle(), provider=request.ref.provider)
            resolution_error = None
            try:
                credential = await self._resolved_from_row(
                    session,
                    row=row,
                    principal=request.principal,
                    required_scopes=request.required_scopes,
                    rejected_token_digest=request.rejected_token_digest,
                )
            except IntegrationError as exc:
                # A rotating refresh token may already have been exchanged. Keep
                # that encrypted update even if the provider narrowed its scopes.
                resolution_error = exc
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
        except ConnectionUnresolvedError:
            return ConnectionStatus(ref=ref, status="missing")
        except IntegrationError:
            return ConnectionStatus(ref=ref, status="unavailable")
        return ConnectionStatus(
            ref=ref,
            status="ready",
            granted_scopes=credential.granted_scopes,
            account=credential.account,
        )

    async def _select_authorized_candidate(
        self,
        candidates: list[Connection],
        request: ConnectionResolutionRequest,
    ) -> Connection | None:
        own: list[Connection] = []
        instance: list[Connection] = []
        shared: list[Connection] = []
        for row in candidates:
            if row.ownership_mode == ConnectionOwnershipMode.INSTANCE.value:
                instance.append(row)
            elif request.principal.user_id is not None and str(row.owner_id) == str(request.principal.user_id):
                own.append(row)
            else:
                shared.append(row)
        # An owned record shadows the instance fallback. If its execution
        # policy denies this principal, do not silently switch identities by
        # resolving an instance credential with the same handle.
        for group in (own, instance):
            if not group:
                continue
            row = group[0]
            authorization_error = self.authorize_principal(
                request,
                connection_owner_id=str(row.owner_id) if row.owner_id is not None else None,
                owner_kind=row.ownership_mode,
                allow_non_interactive=row.allow_non_interactive,
            )
            if authorization_error is None and row.ownership_mode == ConnectionOwnershipMode.INSTANCE.value:
                authorization_error = await self.authorize_instance_connection(request, row=row)
            if authorization_error is not None:
                await _audit_resolution_denial(request, row=row, error=authorization_error)
                raise authorization_error
            return row
        if request.principal.user_id is None or not shared:
            return None
        # Owner-only families (legacy MCP transports, the authenticated A2A
        # sub-path) never admit a delegated caller, so they must not reach a
        # shared row either -- otherwise a share would be a wider grant through
        # MCP than through the route the share was made for.
        if not request.principal.allow_explicit_shares:
            return None
        shared = [row for row in shared if request.principal.interactive or row.allow_non_interactive]
        if not shared:
            return None
        settings = get_settings_service()
        authz = get_authorization_service()
        if not settings.auth_settings.AUTHZ_ENABLED or not await authz.supports_cross_user_fetch():
            return None
        try:
            user_id = UUID(str(request.principal.user_id))
        except ValueError:
            return None
        decisions = await authz.batch_enforce(
            user_id=user_id,
            domain="*",
            requests=[(f"connection:{row.id}", "execute") for row in shared],
            context={"execution_principal_kind": request.principal.kind},
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

    async def _resolved_from_row(
        self,
        session: AsyncSession,
        *,
        row: Connection,
        principal: ExecutionPrincipal,
        required_scopes: frozenset[str],
        rejected_token_digest: str | None = None,
    ) -> ResolvedCredential:
        request = ConnectionResolutionRequest(
            ref=ConnectionRef(provider=row.provider_key, name=row.name),
            principal=principal,
            required_scopes=required_scopes,
        )
        portable_error = self.authorize_principal(
            request,
            connection_owner_id=str(row.owner_id) if row.owner_id is not None else None,
            owner_kind=row.ownership_mode,
            allow_non_interactive=row.allow_non_interactive,
        )
        if portable_error is not None:
            is_explicit_share = (
                row.ownership_mode == ConnectionOwnershipMode.USER.value
                and principal.user_id is not None
                and str(row.owner_id) != str(principal.user_id)
                # Owner-only families never widen the floor for a share, even when
                # the host authorization service would have approved one.
                and principal.allow_explicit_shares
            )
            # The portable floor deliberately reports an owner mismatch for a
            # shared connection. Callers reach this private method only after
            # the host authorization service has approved that share. Every
            # other portable denial, including anonymous and non-interactive
            # use without the per-connection opt-in, remains authoritative.
            if not is_explicit_share or (not principal.interactive and not row.allow_non_interactive):
                await _audit_resolution_denial(request, row=row, error=portable_error)
                raise portable_error
        if row.status == PersistedConnectionStatus.REVOKED.value:
            raise ConnectionUnresolvedError(request.ref.to_handle(), provider=row.provider_key)
        secret = await session.get(ConnectionSecret, row.id)
        if secret is None:
            raise ConnectionUnresolvedError(request.ref.to_handle(), provider=row.provider_key)
        try:
            payload = _decrypt_credential_payload(secret.encrypted_payload)
        except ConnectionSecretError as exc:
            raise ConnectionUnresolvedError(request.ref.to_handle(), provider=row.provider_key) from exc
        try:
            payload = await broker.refresh_if_needed(session, row, payload, rejected_token_digest=rejected_token_digest)
        except OAuthError:
            raise AuthExpiredError(provider=row.provider_key) from None
        expires_at = _parse_expiry(payload.get("expires_at"))
        if expires_at is not None and expires_at <= _utc_now():
            raise AuthExpiredError(provider=row.provider_key)
        granted = frozenset(row.granted_scopes)
        missing = required_scopes - granted
        if missing:
            raise ScopeMissingError(missing, provider=row.provider_key)
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
                "has_credentials": has_credentials,
            }
        )
