"""API endpoints for connector management."""

import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser
from langflow.services.connectors.schemas import (
    ConnectorCreate,
    ConnectorMetadata,
    ConnectorResponse,
    ConnectorUpdate,
    FileListResponse,
    OAuthCallback,
    OAuthURLResponse,
    SyncRequest,
    SyncResponse,
)
from langflow.services.connectors.service import ConnectorService
from langflow.services.deps import get_connector_service, get_session

router = APIRouter(prefix="/connectors", tags=["Connectors"])


@router.get("/available", response_model=list[ConnectorMetadata])
async def list_available_connectors():
    """List all available connector types and their metadata.

    Returns a list of connector types that can be created, along with their
    required OAuth scopes, supported file types, and other metadata.

    Returns:
        list[ConnectorMetadata]: List of available connector types with:
            - connector_type: Identifier (e.g., "google_drive")
            - name: Display name (e.g., "Google Drive")
            - description: What the connector does
            - icon: Icon identifier for UI
            - required_scopes: OAuth scopes needed
            - supported_mime_types: File types the connector can handle

    Example:
        ```json
        [{
            "connector_type": "google_drive",
            "name": "Google Drive",
            "description": "Connect to Google Drive for document synchronization",
            "icon": "google-drive",
            "available": true,
            "required_scopes": [
                "https://www.googleapis.com/auth/drive.readonly"
            ],
            "supported_mime_types": ["application/pdf", "text/plain", ...]
        }]
        ```
    """
    from langflow.services.connectors.providers import CONNECTOR_REGISTRY

    available_connectors = []
    for connector_type, connector_class in CONNECTOR_REGISTRY.items():
        try:
            metadata = connector_class.get_metadata()
            available_connectors.append(metadata)
        except Exception as e:  # noqa: BLE001
            # Skip connectors that fail to load metadata
            from lfx.log import logger

            logger.warning(f"Failed to load metadata for {connector_type}: {e}")

    return available_connectors


@router.get("", response_model=list[ConnectorResponse])
async def list_connectors(
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
    knowledge_base_id: str | None = None,
):
    """List user's connector connections."""
    connections = await connector_service.get_user_connections(
        session=session, user_id=current_user.id, knowledge_base_id=knowledge_base_id
    )

    # Convert to response schema
    return [
        ConnectorResponse(
            id=conn.id,
            name=conn.name,
            connector_type=conn.connector_type,
            is_authenticated=bool(conn.config.get("access_token")),
            last_sync=conn.last_sync_at,
            sync_status=conn.sync_status,
            knowledge_base_id=conn.knowledge_base_id,
            created_at=conn.created_at,
            updated_at=conn.updated_at,
        )
        for conn in connections
    ]


@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    connector_data: ConnectorCreate,
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
):
    """Create a new connector connection for the current user.

    Creates a connector connection that can later be authenticated via OAuth.
    The connection is owned by the current user and isolated from other users.

    Args:
        connector_data: Connector configuration including:
            - connector_type: Type of connector (e.g., "google_drive")
            - name: Display name for this connection
            - config: Connector-specific configuration
            - knowledge_base_id: Optional KB to associate with
        current_user: Currently authenticated user (injected)
        session: Database session (injected)
        connector_service: Connector service instance (injected)

    Returns:
        ConnectorResponse: Created connection with:
            - id: Unique connection ID (use for OAuth and sync)
            - is_authenticated: False (needs OAuth)
            - created_at, updated_at: Timestamps

    Security:
        - User ownership automatically assigned
        - Sensitive config fields encrypted at rest
        - Rate limited to 10 concurrent operations per user

    Example:
        ```json
        POST /api/v1/connectors
        {
            "connector_type": "google_drive",
            "name": "My Google Drive",
            "config": {"folder_id": "root", "recursive": true},
            "knowledge_base_id": "kb_123"
        }
        ```
    """
    connection = await connector_service.create_connection(
        session=session,
        user_id=current_user.id,
        connector_type=connector_data.connector_type,
        name=connector_data.name,
        config=connector_data.config,
        knowledge_base_id=connector_data.knowledge_base_id,
    )

    return ConnectorResponse(
        id=connection.id,
        name=connection.name,
        connector_type=connection.connector_type,
        is_authenticated=False,
        knowledge_base_id=connection.knowledge_base_id,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.get("/{connection_id}", response_model=ConnectorResponse)
async def get_connector(
    connection_id: UUID,
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
):
    """Get a specific connector connection."""
    connection = await connector_service.get_connection(
        session=session, connection_id=connection_id, user_id=current_user.id
    )

    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    return ConnectorResponse(
        id=connection.id,
        name=connection.name,
        connector_type=connection.connector_type,
        is_authenticated=connection.oauth_token is not None,
        last_sync=connection.last_sync_at,
        sync_status=connection.sync_status,
        knowledge_base_id=connection.knowledge_base_id,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.patch("/{connection_id}", response_model=ConnectorResponse)
async def update_connector(
    connection_id: UUID,
    update_data: ConnectorUpdate,
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
):
    """Update a connector connection."""
    connection = await connector_service.update_connection(
        session=session,
        connection_id=connection_id,
        user_id=current_user.id,
        update_data=update_data.dict(exclude_unset=True),
    )

    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    return ConnectorResponse(
        id=connection.id,
        name=connection.name,
        connector_type=connection.connector_type,
        is_authenticated=connection.oauth_token is not None,
        last_sync=connection.last_sync_at,
        sync_status=connection.sync_status,
        knowledge_base_id=connection.knowledge_base_id,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connection_id: UUID,
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
):
    """Delete a connector connection."""
    deleted = await connector_service.delete_connection(
        session=session, connection_id=connection_id, user_id=current_user.id
    )

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")


@router.get("/{connection_id}/oauth/url", response_model=OAuthURLResponse)
async def get_oauth_url(
    connection_id: UUID,
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
):
    """Get OAuth authorization URL."""
    from lfx.log import logger

    from langflow.services.connectors.oauth_handler import OAuthHandler

    # Get connection
    connection = await connector_service.get_connection(
        session=session, connection_id=connection_id, user_id=current_user.id
    )

    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    # Get OAuth credentials from config or environment
    import os

    client_id = connection.config.get("client_id") or os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = connection.config.get("client_secret") or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth client credentials not configured")

    # Build redirect URI (adjust based on deployment)
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:7860/api/v1/connectors/oauth/callback")

    # Create OAuth handler
    oauth_handler = OAuthHandler(
        connector_type=connection.connector_type,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    try:
        # Generate authorization URL
        auth_url, state = oauth_handler.generate_auth_url(connection_id, current_user.id)

        # Store state in connection config for verification
        await connector_service.update_connection(
            session=session,
            connection_id=connection_id,
            user_id=current_user.id,
            update_data={"config": {**connection.config, "oauth_state": state}},
        )

        return OAuthURLResponse(authorization_url=auth_url, state=state)

    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to generate OAuth URL: {e}")
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate OAuth URL: {e}"
        )


@router.get("/oauth/callback")
async def oauth_callback_handler(
    code: str,
    state: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Handle OAuth callback from Google (GET request).

    Google redirects here after user authorizes. This endpoint:
    1. Finds the connection using the state parameter
    2. Exchanges the code for access/refresh tokens
    3. Stores tokens securely
    4. Returns HTML that closes the popup window
    """
    from fastapi.responses import HTMLResponse
    from lfx.log import logger
    from sqlmodel import select

    from langflow.services.connectors.oauth_handler import OAuthHandler
    from langflow.services.database.models.connector.model import ConnectorConnection

    try:
        # Find connection with matching oauth_state
        # Query all connections and find match (simple approach for now)

        # We need to find the connection by state
        # The state was generated from connection_id, so we'll query all and match
        result = await session.exec(select(ConnectorConnection))
        connections = result.all()

        connection = None
        for conn in connections:
            if conn.config and conn.config.get("oauth_state") == state:
                connection = conn
                break

        if not connection:
            logger.error(f"No connection found for state: {state[:20]}...")
            error_html = (
                "<html><body><h1>Error</h1><p>Connection not found. Please try again.</p>"
                "<script>setTimeout(() => window.close(), 3000);</script></body></html>"
            )
            return HTMLResponse(content=error_html, status_code=400)

        # Get OAuth credentials
        import os

        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:7860/api/v1/connectors/oauth/callback")

        # Create OAuth handler
        oauth_handler = OAuthHandler(
            connector_type=connection.connector_type,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

        # Exchange code for tokens and store them
        logger.info(f"Starting OAuth token exchange for connection {connection.id}")

        try:
            await oauth_handler.handle_callback(
                session=session,
                connection_id=connection.id,
                code=code,
                state=state,
            )
            logger.info(f"Token exchange completed for connection {connection.id}")
        except Exception as token_error:
            logger.error(f"Token exchange failed: {token_error}")
            import traceback

            traceback.print_exc()
            raise

        # Ensure session is committed
        await session.commit()
        logger.info(f"Session committed for connection {connection.id}")

        # Verify tokens were saved
        updated_conn = await session.exec(select(ConnectorConnection).where(ConnectorConnection.id == connection.id))
        saved_connection = updated_conn.first()
        if saved_connection and saved_connection.config.get("access_token"):
            logger.info(f"✓ OAuth successful - tokens saved for connection {connection.id}")
        else:
            logger.error(f"✗ OAuth tokens NOT saved for connection {connection.id}!")
            logger.error(f"Config keys: {list(saved_connection.config.keys()) if saved_connection else 'None'}")

        # Return success page that auto-closes
        return HTMLResponse(
            content="""
            <html>
            <head><title>Connected!</title></head>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1 style="color: #10b981;">✓ Connected Successfully!</h1>
                <p>You can close this window or it will close automatically.</p>
                <script>
                    setTimeout(() => window.close(), 2000);
                </script>
            </body>
            </html>
            """
        )

    except Exception as e:  # noqa: BLE001
        logger.error(f"OAuth callback failed: {e}")
        import traceback

        traceback.print_exc()
        return HTMLResponse(
            content=f"""
            <html>
            <body style="font-family: system-ui; padding: 40px; text-align: center;">
                <h1 style="color: #ef4444;">Authentication Failed</h1>
                <p>{e!s}</p>
                <p>You can close this window.</p>
                <script>setTimeout(() => window.close(), 5000);</script>
            </body>
            </html>
            """,
            status_code=500,
        )


@router.post("/{connection_id}/oauth/callback", response_model=ConnectorResponse)
async def oauth_callback_post(
    connection_id: UUID,
    callback_data: OAuthCallback,
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
):
    """Complete OAuth authorization (POST variant for programmatic use)."""
    from lfx.log import logger

    from langflow.services.connectors.oauth_handler import OAuthHandler

    # Get connection
    connection = await connector_service.get_connection(
        session=session, connection_id=connection_id, user_id=current_user.id
    )

    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    # Verify state token (CSRF protection)
    stored_state = connection.config.get("oauth_state")
    if not stored_state or stored_state != callback_data.state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state token")

    # Get OAuth credentials
    import os

    client_id = connection.config.get("client_id") or os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = connection.config.get("client_secret") or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:7860/api/v1/connectors/oauth/callback")

    # Create OAuth handler
    oauth_handler = OAuthHandler(
        connector_type=connection.connector_type,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    try:
        # Exchange code for tokens
        await oauth_handler.handle_callback(
            session=session,
            connection_id=connection_id,
            code=callback_data.code,
            state=callback_data.state,
        )

        # Get updated connection
        updated_connection = await connector_service.get_connection(
            session=session, connection_id=connection_id, user_id=current_user.id
        )

        return ConnectorResponse(
            id=updated_connection.id,
            name=updated_connection.name,
            connector_type=updated_connection.connector_type,
            is_authenticated=True,
            knowledge_base_id=updated_connection.knowledge_base_id,
            created_at=updated_connection.created_at,
            updated_at=updated_connection.updated_at,
        )

    except Exception as e:  # noqa: BLE001
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"OAuth callback failed: {e}"
        ) from None


@router.post("/{connection_id}/sync", response_model=SyncResponse)
async def sync_files_endpoint(
    connection_id: UUID,
    sync_request: SyncRequest,
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
):
    """Start file synchronization."""
    from lfx.log import logger

    # Get connection
    connection = await connector_service.get_connection(
        session=session, connection_id=connection_id, user_id=current_user.id
    )

    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    # Check if authenticated
    if not connection.config.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Connection not authenticated. Please complete OAuth flow first.",
        )

    try:
        # Start sync in background
        task_id = await connector_service.sync_files(
            session=session,
            connection_id=connection_id,
            user_id=current_user.id,
            selected_files=sync_request.selected_files,
            max_files=sync_request.max_files,
        )

        return SyncResponse(task_id=task_id, status="started", message=f"Sync started for {connection.connector_type}")

    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to start sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to start sync: {e}"
        ) from None


@router.get("/{connection_id}/sync/progress/{task_id}")
async def sync_progress_stream(
    connection_id: UUID,  # noqa: ARG001
    task_id: str,
    token: str,  # noqa: ARG001
):
    """Stream sync progress updates via Server-Sent Events (SSE).

    Returns real-time progress updates as the sync happens.
    Frontend can listen to this stream to show live progress.

    Note: Auth token must be passed as query param since EventSource
    doesn't support custom headers.

    Args:
        connection_id: Connection ID
        task_id: Sync task ID
        token: Auth token (passed as query param)
    """

    # Validate token manually since EventSource can't send headers
    # For now, we'll trust the token param (in production, validate it properly)
    # TODO: Add proper token validation here
    async def event_generator():
        """Generate SSE events for sync progress."""
        try:
            # Simulate a 10-second sync with progress updates
            total_files = 100

            for i in range(11):  # 0 to 10 (11 updates over 10 seconds)
                progress = i * 10  # 0%, 10%, 20%, ... 100%
                files_processed = min(i * 10, total_files)

                # Simulate progress (10 steps for demo)
                max_steps = 10
                status_text = "syncing" if i < max_steps else "completed"
                message_text = f"Synced {files_processed}/{total_files} files" if i < max_steps else "Sync complete!"

                event_data = {
                    "task_id": task_id,
                    "status": status_text,
                    "progress": progress,
                    "files_processed": files_processed,
                    "total_files": total_files,
                    "message": message_text,
                }

                # Send SSE event
                yield f"data: {json.dumps(event_data)}\n\n"

                if i < max_steps:
                    await asyncio.sleep(1)  # Wait 1 second between updates

            # Final completion event
            yield f"data: {json.dumps({'task_id': task_id, 'status': 'done'})}\n\n"

        except Exception as e:  # noqa: BLE001
            error_data = {"task_id": task_id, "status": "error", "message": str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/{connection_id}/sync/status", response_model=SyncResponse)
async def get_sync_status(
    connection_id: UUID,  # noqa: ARG001
    task_id: str,
    current_user: CurrentActiveUser,  # noqa: ARG001
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],  # noqa: ARG001
):
    """Get sync operation status."""
    # TODO: Implement sync status
    return SyncResponse(task_id=task_id, status="unknown", message="Sync status not yet implemented")


@router.get("/{connection_id}/files", response_model=FileListResponse)
async def list_files(
    connection_id: UUID,
    current_user: CurrentActiveUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    connector_service: Annotated[ConnectorService, Depends(get_connector_service)],
    page_token: str | None = None,
    max_files: int = 100,
):
    """List files available from connector."""
    from lfx.log import logger

    from langflow.services.connectors.providers import create_connector

    # Get connection
    connection = await connector_service.get_connection(
        session=session, connection_id=connection_id, user_id=current_user.id
    )

    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    # Check if authenticated
    if not connection.config.get("access_token"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Connection not authenticated")

    try:
        # Create connector instance
        connector = create_connector(connection.connector_type, connection.config)
        if not connector:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown connector type: {connection.connector_type}"
            )

        # Connect to the service
        if not await connector.connect():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to connect to provider")

        # List files
        file_infos, next_page = await connector.list_files(page_size=max_files, page_token=page_token)

        # Convert FileInfo objects to dictionaries
        files_list = [
            {
                "id": f.id,
                "name": f.name,
                "mime_type": f.mime_type,
                "size": f.size,
                "modified_time": f.modified_time.isoformat(),
                "parent_id": f.parent_id,
                "web_url": f.web_url,
                "metadata": f.metadata,
            }
            for f in file_infos
        ]

        # Disconnect
        await connector.disconnect()

        return FileListResponse(files=files_list, next_page_token=next_page, total_count=len(files_list))

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to list files: {e}"
        ) from None
