"""Owner- and share-aware API for persisted integration connections."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from lfx.integrations.errors import IntegrationPolicyBlockedError
from lfx.integrations.models import PROVIDER_ID_PATTERN
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.integration_policy import IntegrationPolicyPurpose, aresolve_integration_policy
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.v1.model_provider_policy_scope import ProviderPolicyAttributesDependency
from langflow.services.authorization import ConnectionAction, ensure_connection_permission
from langflow.services.authorization.guards import audit_guard_in_transaction
from langflow.services.connection import ConnectionConflictError, DatabaseConnectionResolverService
from langflow.services.connection.oauth import broker as oauth_broker
from langflow.services.connection.oauth.config import OAuthError, OAuthRegistration, get_oauth_settings
from langflow.services.connection.service import enforce_integration_policy_for_provider
from langflow.services.database.models.connection import (
    Connection,
    ConnectionCreate,
    ConnectionOwnershipMode,
    ConnectionRead,
    ConnectionTestRequest,
    ConnectionUpdate,
)
from langflow.services.database.models.connection.schemas import ConnectionRevokeRead
from langflow.services.deps import get_connection_resolver_service, session_scope
from langflow.services.rate_limit import check_rate_limit


class _ConnectionRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            if "/connections/oauth/" in request.scope["path"] and request.scope["path"].endswith("/callback"):
                # Cache the callback parameters for the handler, then remove
                # them before dependency errors or access logs can render URLs.
                _ = request.query_params
                request.scope["query_string"] = b""
            return await handler(request)

        return safe_handler


router = APIRouter(prefix="/connections", tags=["Connections"], route_class=_ConnectionRoute)

# Every user can see and use instance connections, but only superusers create
# them, so only superusers may change, re-authorize, or remove them. This floor
# holds even when authorization is disabled or a plugin would allow the action.
_INSTANCE_OPERATOR_ACTIONS = frozenset({ConnectionAction.WRITE, ConnectionAction.DELETE})

# Rate-limit counter namespaces. The endpoints that trigger outbound provider
# calls get their own buckets so a burst of OAuth or health traffic cannot
# consume a client's budget for ordinary CRUD, and so the unauthenticated
# callback cannot block a user's ability to start a consent flow.
_SCOPE_CONNECTIONS = "connections"
_SCOPE_CONNECTION_TEST = "connections-test"
_SCOPE_CONNECTION_HEALTH = "connections-health"
_SCOPE_CONNECTION_OAUTH_START = "connections-oauth-start"
_SCOPE_CONNECTION_OAUTH_CALLBACK = "connections-oauth-callback"

_OAUTH_NONCE_LENGTH = 43
_OAUTH_MAX_CODE_LENGTH = 8192
_OAUTH_RESPONSE_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class OAuthStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registration_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    scopes: list[str] = Field(min_length=1, max_length=512)


class OAuthStartResponse(BaseModel):
    authorization_url: str


class OAuthRegistrationRead(BaseModel):
    """One operator-configured registration, as a connection picker may show it.

    Credential-free by construction: the client id, the client secret or private
    key, and the redirect URI stay on the server. A caller needs the id to name
    the registration in a start request, and the scope ceiling to know which
    subset it may ask for.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    profile: Literal["user", "bot"]
    context: Literal["self_managed", "hosted", "desktop"]
    client_type: Literal["confidential", "public"]
    scopes: list[str] = Field(description="The operator's ceiling; a start request selects a nonempty subset.")
    allowed_tenants: list[str] = Field(description="Workspaces or domains the provider account must belong to.")


class OAuthRegistrationListRead(BaseModel):
    registrations: list[OAuthRegistrationRead]


def _oauth_cookie(state_value: str) -> str:
    return "lf_connection_oauth_" + oauth_broker.digest(state_value)[:24]


def _database_service() -> DatabaseConnectionResolverService:
    service = get_connection_resolver_service()
    if not isinstance(service, DatabaseConnectionResolverService):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connection metadata is managed by the configured host service.",
        )
    return service


ConnectionService = Annotated[DatabaseConnectionResolverService, Depends(_database_service)]


def _policy_blocked(exc: IntegrationPolicyBlockedError) -> HTTPException:
    """Return the sanitized 403 for an integration the deployment policy denies."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error_code": exc.code,
            "message": exc.safe_message,
            "hint": exc.hint,
            "provider": exc.provider,
        },
    )


def _interactive_principal(user: CurrentActiveUser) -> ExecutionPrincipal:
    return ExecutionPrincipal(
        kind="actor",
        user_id=str(user.id),
        actor_id=str(user.id),
        family="connections_api",
        interactive=True,
        actor_label=user.username,
    )


async def _visible_row(
    *,
    service: DatabaseConnectionResolverService,
    session: AsyncSession,
    user: CurrentActiveUser,
    connection_id: UUID,
    action: ConnectionAction,
) -> Connection:
    row = await service.get_for_user(session, user=user, connection_id=connection_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    if (
        row.ownership_mode == ConnectionOwnershipMode.INSTANCE.value
        and action in _INSTANCE_OPERATOR_ACTIONS
        and not user.is_superuser
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a superuser may change or remove an instance connection.",
        )
    await ensure_connection_permission(
        user,
        action,
        connection_id=row.id,
        connection_owner_id=row.owner_id,
    )
    return row


async def _authorized_row(
    *,
    service: DatabaseConnectionResolverService,
    session: DbSession | DbSessionReadOnly,
    user: CurrentActiveUser,
    connection_id: UUID,
    action: ConnectionAction,
    for_update: bool = False,
) -> Connection:
    if not for_update:
        return await _visible_row(
            service=service, session=session, user=user, connection_id=connection_id, action=action
        )
    # Taking the lock writes the row, so authorize in a separate read
    # transaction first: a caller who may not act on this connection must
    # never hold its lock, even briefly on the way to a 404 or 403.
    async with session_scope() as read_session:
        authorized = await _visible_row(
            service=service, session=read_session, user=user, connection_id=connection_id, action=action
        )
        authorized_owner = (authorized.ownership_mode, authorized.owner_id)
    # get_for_user repeats the scoped lookup under the lock. Fail closed if the
    # row disappeared or changed owner after the permission check.
    row = await service.get_for_user(session, user=user, connection_id=connection_id, for_update=True)
    if row is None or (row.ownership_mode, row.owner_id) != authorized_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    # Ownership can stay unchanged while the plugin's policy is revoked.
    # Recheck after acquiring the lock; durable audit must use this transaction
    # (or release it on denial) rather than wait on another SQLite writer.
    async with audit_guard_in_transaction(session):
        await ensure_connection_permission(
            user,
            action,
            connection_id=row.id,
            connection_owner_id=row.owner_id,
        )
    return row


def _may_enable_non_interactive(user: CurrentActiveUser, row: Connection) -> bool:
    """Only a credential's owner may widen it to unattended executions."""
    if row.ownership_mode == ConnectionOwnershipMode.INSTANCE.value:
        return bool(user.is_superuser)
    return str(row.owner_id) == str(user.id)


@router.get("", response_model=list[ConnectionRead])
async def list_connections(
    request: Request,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    service: ConnectionService,
    provider: Annotated[str | None, Query(pattern=PROVIDER_ID_PATTERN, max_length=120)] = None,
) -> list[ConnectionRead]:
    """List owned, instance-owned, and explicitly shared connection metadata."""
    check_rate_limit(request, scope=_SCOPE_CONNECTIONS)
    return await service.list_for_user(session, user=current_user, provider_key=provider)


@router.post("", response_model=ConnectionRead, status_code=status.HTTP_201_CREATED)
async def create_connection(
    request: Request,
    payload: ConnectionCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Create connection metadata and optionally store encrypted credentials."""
    check_rate_limit(request, scope=_SCOPE_CONNECTIONS)
    if payload.ownership_mode.value == "instance" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a superuser may create an instance connection.",
        )
    await ensure_connection_permission(
        current_user,
        ConnectionAction.CREATE,
        connection_owner_id=current_user.id,
    )
    try:
        return await service.create(session, user=current_user, payload=payload)
    except IntegrationPolicyBlockedError as exc:
        raise _policy_blocked(exc) from exc
    except ConnectionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{connection_id}/test", response_model=ConnectionRead)
async def test_connection(
    request: Request,
    connection_id: UUID,
    payload: ConnectionTestRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Validate the local credential envelope and requested scope coverage."""
    check_rate_limit(request, scope=_SCOPE_CONNECTION_TEST)
    row = await _authorized_row(
        service=service,
        session=session,
        user=current_user,
        connection_id=connection_id,
        action=ConnectionAction.EXECUTE,
        for_update=True,
    )
    try:
        await enforce_integration_policy_for_provider(row.provider_key, user_id=current_user.id)
    except IntegrationPolicyBlockedError as exc:
        raise _policy_blocked(exc) from exc
    return await service.check_health(
        session,
        row=row,
        principal=_interactive_principal(current_user),
        required_scopes=frozenset(payload.required_scopes),
    )


@router.post("/{connection_id}/health", response_model=ConnectionRead)
async def refresh_connection_health(
    request: Request,
    connection_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Refresh credential health without returning or logging token material."""
    check_rate_limit(request, scope=_SCOPE_CONNECTION_HEALTH)
    row = await _authorized_row(
        service=service,
        session=session,
        user=current_user,
        connection_id=connection_id,
        action=ConnectionAction.EXECUTE,
        for_update=True,
    )
    try:
        await enforce_integration_policy_for_provider(row.provider_key, user_id=current_user.id)
    except IntegrationPolicyBlockedError as exc:
        raise _policy_blocked(exc) from exc
    return await service.check_health(
        session,
        row=row,
        principal=_interactive_principal(current_user),
    )


@router.patch("/{connection_id}", response_model=ConnectionRead)
async def update_connection(
    request: Request,
    connection_id: UUID,
    payload: ConnectionUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Rename a connection or change its non-interactive opt-in without re-authorizing.

    Anyone who may write the connection may withdraw the opt-in. Granting it
    widens which executions reach the owner's account, so only the owner (a
    superuser, for an instance connection) may turn it on.
    """
    check_rate_limit(request, scope=_SCOPE_CONNECTIONS)
    row = await _authorized_row(
        service=service,
        session=session,
        user=current_user,
        connection_id=connection_id,
        action=ConnectionAction.WRITE,
        for_update=True,
    )
    if (
        payload.allow_non_interactive
        and not row.allow_non_interactive
        and not _may_enable_non_interactive(current_user, row)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the connection owner may allow non-interactive use.",
        )
    return await service.update(session, row, payload)


@router.post("/{connection_id}/revoke", response_model=ConnectionRevokeRead)
async def revoke_connection(
    request: Request,
    connection_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Revoke at the provider when supported and always remove local credentials."""
    check_rate_limit(request, scope=_SCOPE_CONNECTIONS)
    row = await _authorized_row(
        service=service,
        session=session,
        user=current_user,
        connection_id=connection_id,
        action=ConnectionAction.WRITE,
        for_update=True,
    )
    return await service.revoke(session, row)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    request: Request,
    connection_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> Response:
    check_rate_limit(request, scope=_SCOPE_CONNECTIONS)
    row = await _authorized_row(
        service=service,
        session=session,
        user=current_user,
        connection_id=connection_id,
        action=ConnectionAction.DELETE,
        for_update=True,
    )
    await service.delete(session, row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{connection_id}/oauth/start")
async def start_connection_oauth(
    request: Request,
    connection_id: UUID,
    payload: OAuthStartRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
    response: Response,
) -> OAuthStartResponse:
    """Authorize an instance-configured registration for an existing connection."""
    check_rate_limit(request, scope=_SCOPE_CONNECTION_OAUTH_START)
    row = await _authorized_row(
        service=service,
        session=session,
        user=current_user,
        connection_id=connection_id,
        action=ConnectionAction.WRITE,
        for_update=True,
    )
    # A blocked provider must not reach the authorization screen: refuse before
    # the broker mints state or sets a browser-binding cookie.
    try:
        await enforce_integration_policy_for_provider(row.provider_key, user_id=current_user.id)
    except IntegrationPolicyBlockedError as exc:
        raise _policy_blocked(exc) from exc
    try:
        url, state_value, browser = await oauth_broker.start(
            session, row=row, user_id=current_user.id, registration_id=payload.registration_id, scopes=payload.scopes
        )
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    registration = get_oauth_settings().registration(payload.registration_id)
    response.set_cookie(
        _oauth_cookie(state_value),
        browser,
        httponly=True,
        secure=registration.redirect_uri.startswith("https:"),
        samesite="lax",
        max_age=600,
        path="/api/v1/connections/oauth",
    )
    response.headers.update(_OAUTH_RESPONSE_HEADERS)
    return OAuthStartResponse(authorization_url=url)


@router.get("/oauth/registrations", response_model=OAuthRegistrationListRead)
async def list_oauth_registrations(
    request: Request,
    current_user: CurrentActiveUser,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
    response: Response,
    provider: Annotated[str | None, Query(pattern=PROVIDER_ID_PATTERN, max_length=120)] = None,
) -> OAuthRegistrationListRead:
    """List the registrations a caller may name in an authorization request.

    Registration configuration is operator-only, so a client had no way to learn
    the ids that ``POST /connections/{connection_id}/oauth/start`` accepts, or the
    scope ceiling it must stay inside. Only availability and non-secret fields are
    returned, and a registration that this deployment would refuse is omitted
    rather than advertised: a picker must not offer consent that cannot start.
    """
    check_rate_limit(request, scope=_SCOPE_CONNECTIONS)
    # The list is filtered per caller, so a shared cache must never replay one
    # user's answer to another.
    response.headers["Cache-Control"] = "no-store"
    settings = get_oauth_settings()
    available: list[tuple[str, OAuthRegistration]] = []
    for registration_id in settings.registration_ids():
        try:
            registration = settings.registration(registration_id)
        except OAuthError:
            # Invalid, or configured for another deployment context. The start
            # request would raise the same error, so leave it out.
            continue
        if provider is not None and registration.provider != provider:
            continue
        available.append((registration_id, registration))

    if not available:
        return OAuthRegistrationListRead(registrations=[])

    # A provider outside the operator's integration ceiling is refused at
    # oauth/start, so it must not appear here either.
    policy = await aresolve_integration_policy(
        user_id=current_user.id,
        provider_ids=frozenset(registration.provider for _, registration in available),
        purpose=IntegrationPolicyPurpose.DISCOVER,
        attributes=provider_policy_attributes,
    )
    return OAuthRegistrationListRead(
        registrations=[
            OAuthRegistrationRead(
                id=registration_id,
                provider=registration.provider,
                profile=registration.profile,
                context=registration.context,
                client_type=registration.client_type,
                scopes=list(registration.scopes),
                allowed_tenants=list(registration.allowed_tenants),
            )
            for registration_id, registration in available
            if policy.allows_provider(registration.provider)
        ]
    )


@router.get("/oauth/{provider}/callback", response_class=HTMLResponse)
async def complete_connection_oauth(provider: str, request: Request, service: ConnectionService) -> HTMLResponse:
    """Terminate provider callbacks here; state and browser binding replace login."""
    _ = service  # Respect host-managed connection services at the callback too.
    check_rate_limit(request, scope=_SCOPE_CONNECTION_OAUTH_CALLBACK)
    query = request.query_params
    # Uvicorn derives its access-log target from this shared scope at response time.
    # Never leave the authorization code or state in that target.
    request.scope["query_string"] = b""
    state_value, code = query.get("state", ""), query.get("code")
    browser = request.cookies.get(_oauth_cookie(state_value), "")
    response = HTMLResponse("Connection authorized. You may close this window.", headers=_OAUTH_RESPONSE_HEADERS)
    response.delete_cookie(_oauth_cookie(state_value), path="/api/v1/connections/oauth")
    try:
        if (
            len(state_value) != _OAUTH_NONCE_LENGTH
            or not browser
            or len(browser) != _OAUTH_NONCE_LENGTH
            or (code is not None and len(code) > _OAUTH_MAX_CODE_LENGTH)
            or len(query.getlist("state")) != 1
            or len(query.getlist("code")) > 1
        ):
            msg = "OAuth callback is invalid, expired, or already used."
            raise OAuthError(msg)
        await oauth_broker.complete(
            provider=provider, state=state_value, browser=browser, code=code, denied="error" in query
        )
    except OAuthError:
        response.status_code = 400
        response.body = b"OAuth authorization failed. Return to connections and start again."
        response.headers["content-length"] = str(len(response.body))
    return response
