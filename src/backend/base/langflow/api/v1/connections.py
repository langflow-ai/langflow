"""Owner- and share-aware API for persisted integration connections."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from lfx.integrations.errors import IntegrationPolicyBlockedError
from lfx.integrations.models import PROVIDER_ID_PATTERN
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import BaseModel, ConfigDict, Field

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.services.authorization import ConnectionAction, ensure_connection_permission
from langflow.services.connection import ConnectionConflictError, DatabaseConnectionResolverService
from langflow.services.connection.oauth import broker as oauth_broker
from langflow.services.connection.oauth.config import OAuthError, get_oauth_settings
from langflow.services.connection.service import enforce_integration_policy_for_provider
from langflow.services.database.models.connection import (
    Connection,
    ConnectionCreate,
    ConnectionRead,
    ConnectionTestRequest,
)
from langflow.services.database.models.connection.schemas import ConnectionRevokeRead
from langflow.services.deps import get_connection_resolver_service


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


async def _authorized_row(
    *,
    service: DatabaseConnectionResolverService,
    session: DbSession | DbSessionReadOnly,
    user: CurrentActiveUser,
    connection_id: UUID,
    action: ConnectionAction,
    for_update: bool = False,
) -> Connection:
    row = await service.get_for_user(session, user=user, connection_id=connection_id, for_update=for_update)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    await ensure_connection_permission(
        user,
        action,
        connection_id=row.id,
        connection_owner_id=row.owner_id,
    )
    return row


@router.get("", response_model=list[ConnectionRead])
async def list_connections(
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    service: ConnectionService,
    provider: Annotated[str | None, Query(pattern=PROVIDER_ID_PATTERN, max_length=120)] = None,
) -> list[ConnectionRead]:
    """List owned, instance-owned, and explicitly shared connection metadata."""
    return await service.list_for_user(session, user=current_user, provider_key=provider)


@router.post("", response_model=ConnectionRead, status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: ConnectionCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Create connection metadata and optionally store encrypted credentials."""
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
    connection_id: UUID,
    payload: ConnectionTestRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Validate the local credential envelope and requested scope coverage."""
    row = await _authorized_row(
        service=service,
        session=session,
        user=current_user,
        connection_id=connection_id,
        action=ConnectionAction.EXECUTE,
        for_update=True,
    )
    return await service.check_health(
        session,
        row=row,
        principal=_interactive_principal(current_user),
        required_scopes=frozenset(payload.required_scopes),
    )


@router.post("/{connection_id}/health", response_model=ConnectionRead)
async def refresh_connection_health(
    connection_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Refresh credential health without returning or logging token material."""
    row = await _authorized_row(
        service=service,
        session=session,
        user=current_user,
        connection_id=connection_id,
        action=ConnectionAction.EXECUTE,
        for_update=True,
    )
    return await service.check_health(
        session,
        row=row,
        principal=_interactive_principal(current_user),
    )


@router.post("/{connection_id}/revoke", response_model=ConnectionRevokeRead)
async def revoke_connection(
    connection_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Revoke at the provider when supported and always remove local credentials."""
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
    connection_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> Response:
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
    connection_id: UUID,
    payload: OAuthStartRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
    response: Response,
) -> OAuthStartResponse:
    """Authorize an instance-configured registration for an existing connection."""
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


@router.get("/oauth/{provider}/callback", response_class=HTMLResponse)
async def complete_connection_oauth(provider: str, request: Request, service: ConnectionService) -> HTMLResponse:
    """Terminate provider callbacks here; state and browser binding replace login."""
    _ = service  # Respect host-managed connection services at the callback too.
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
