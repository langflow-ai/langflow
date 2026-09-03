"""Owner- and share-aware API for persisted integration connections."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from lfx.integrations.models import PROVIDER_ID_PATTERN
from lfx.services.authorization.base import ExecutionPrincipal

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.services.authorization import ConnectionAction, ensure_connection_permission
from langflow.services.connection import ConnectionConflictError, DatabaseConnectionResolverService
from langflow.services.database.models.connection import (
    Connection,
    ConnectionCreate,
    ConnectionRead,
    ConnectionTestRequest,
)
from langflow.services.deps import get_connection_resolver_service

router = APIRouter(prefix="/connections", tags=["Connections"])


def _database_service() -> DatabaseConnectionResolverService:
    service = get_connection_resolver_service()
    if not isinstance(service, DatabaseConnectionResolverService):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connection metadata is managed by the configured host service.",
        )
    return service


ConnectionService = Annotated[DatabaseConnectionResolverService, Depends(_database_service)]


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


@router.post("/{connection_id}/revoke", response_model=ConnectionRead)
async def revoke_connection(
    connection_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    service: ConnectionService,
) -> ConnectionRead:
    """Remove local credential material and mark the connection revoked."""
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
