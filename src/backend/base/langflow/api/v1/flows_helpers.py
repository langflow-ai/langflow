"""Helper functions for flow CRUD and filesystem operations.

Extracted from flows.py to keep the route-handler module concise.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path as StdlibPath
from typing import TYPE_CHECKING
from uuid import UUID

from aiofile import async_open
from anyio import Path
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from lfx.log import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import normalize_flow_for_export, remove_api_keys
from langflow.services.database.models.base import orjson_dumps
from langflow.services.database.models.flow.model import (
    Flow,
    FlowCreate,
    FlowRead,
    FlowUpdate,
)
from langflow.services.database.models.flow.utils import get_webhook_component_in_flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.utils import get_default_folder_id
from langflow.services.deps import get_settings_service
from langflow.services.storage.service import StorageService

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User


def _get_safe_flow_path(fs_path: str, user_id: UUID, storage_service: StorageService) -> Path:
    """Get a safe filesystem path for flow storage, restricted to user's flows directory.

    Allows both absolute and relative paths, but ensures they're within the user's flows directory.
    """
    if not fs_path:
        raise HTTPException(status_code=400, detail="fs_path cannot be empty")

    # Normalize path separators first (before security checks to prevent backslash bypass)
    normalized_path = fs_path.replace("\\", "/")

    # Reject directory traversal and null bytes (check normalized path)
    if ".." in normalized_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid fs_path: directory traversal (..) is not allowed",
        )
    if "\x00" in normalized_path:
        raise HTTPException(
            status_code=400,
            detail="Invalid fs_path: null bytes are not allowed",
        )

    # Build the safe base directory path
    base_dir = storage_service.data_dir / "flows" / str(user_id)
    base_dir_str = str(base_dir)

    # Normalize base directory path (resolve to absolute, handle symlinks)
    # resolve() doesn't require the path to exist, it just resolves symlinks
    try:
        base_dir_stdlib = StdlibPath(base_dir_str).resolve()
        base_dir_resolved = str(base_dir_stdlib)
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid base directory: {e}") from e

    # Determine if path is absolute (Unix or Windows style)
    is_absolute = normalized_path.startswith("/") or (len(normalized_path) > 1 and normalized_path[1] == ":")

    if is_absolute:
        # Absolute path - resolve and validate it's within base directory
        try:
            requested_path = StdlibPath(normalized_path).resolve()
            requested_resolved = str(requested_path)
            try:
                # Ensure it's a subpath of the base directory
                requested_path.relative_to(base_dir_stdlib)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=(f"Absolute path must be within your flows directory: {base_dir_resolved}"),
                ) from None
            return Path(requested_resolved)
        except (OSError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid file save path: {e}. "
                    f"Verify that the path is within your flows directory: {base_dir_resolved}"
                ),
            ) from e
    else:
        # Relative path - validate that it's within the base directory
        relative_part = normalized_path.lstrip("/")
        safe_path = base_dir / relative_part if relative_part else base_dir
        safe_path_stdlib = base_dir_stdlib / relative_part if relative_part else base_dir_stdlib
        try:
            final_resolved_str = str(safe_path_stdlib.resolve())

            # Ensure resolved path stays within base (prevent symlink attacks)
            if not final_resolved_str.startswith(base_dir_resolved):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid path: resolves outside allowed directory",
                )
        except (OSError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid path: {e}") from e

        return safe_path


def _endpoint_name_was_explicitly_cleared(flow: FlowCreate | FlowUpdate) -> bool:
    """Return whether the request explicitly asked to clear the endpoint name."""
    return "endpoint_name" in flow.model_fields_set and flow.endpoint_name in (None, "")


async def _verify_fs_path(path: str | None, user_id: UUID, storage_service: StorageService) -> None:
    """Verify and prepare the filesystem path for flow storage."""
    if path is not None:
        # Empty strings should be rejected (None is allowed, empty string is not)
        if path == "":
            raise HTTPException(status_code=400, detail="fs_path cannot be empty")
        safe_path = _get_safe_flow_path(path, user_id, storage_service)
        await safe_path.parent.mkdir(parents=True, exist_ok=True)
        if not await safe_path.exists():
            await safe_path.touch()


async def _save_flow_to_fs(flow: Flow, user_id: UUID, storage_service: StorageService) -> None:
    """Save flow data to the filesystem at the validated path."""
    if not flow.fs_path:
        return

    try:
        safe_path = _get_safe_flow_path(flow.fs_path, user_id, storage_service)
        await safe_path.parent.mkdir(parents=True, exist_ok=True)
        # async_open expects a string path, not a Path object
        async with async_open(str(safe_path), "w") as f:
            await f.write(flow.model_dump_json())
    except HTTPException:
        raise
    except OSError as e:
        await logger.aexception("Failed to write flow %s to path %s", flow.name, flow.fs_path)
        raise HTTPException(status_code=500, detail=f"Failed to write flow to filesystem: {e}") from e


async def _new_flow(
    *,
    session: AsyncSession,
    flow: FlowCreate,
    user_id: UUID,
    storage_service: StorageService,
    flow_id: UUID | None = None,
    fail_on_endpoint_conflict: bool = False,
    validate_folder: bool = False,
):
    """Create or upsert a flow.

    Args:
        session: Database session.
        flow: Flow creation data.
        user_id: Owner of the new flow.
        storage_service: Service for filesystem operations.
        flow_id: Allows PUT upsert to create flows with a specific ID for syncing between instances.
        fail_on_endpoint_conflict: PUT should fail predictably on conflicts rather than silently renaming.
        validate_folder: Validates folder_id exists and belongs to user when upserting from external sources.
    """
    try:
        # Validate fs_path if provided (will raise HTTPException if invalid)
        await _verify_fs_path(flow.fs_path, user_id, storage_service)

        # Validate folder_id if requested
        if validate_folder and flow.folder_id is not None:
            folder = (
                await session.exec(select(Folder).where(Folder.id == flow.folder_id, Folder.user_id == user_id))
            ).first()
            if not folder:
                raise HTTPException(status_code=400, detail="Folder not found")

        # Set user_id (ignore any user_id from body for security)
        flow.user_id = user_id

        # Check if the flow.name is unique
        # there might be flows with name like: "MyFlow", "MyFlow (1)", "MyFlow (2)"
        # so we need to check if the name is unique with `like` operator
        # if we find a flow with the same name, we add a number to the end of the name
        # based on the highest number found
        if (await session.exec(select(Flow).where(Flow.name == flow.name).where(Flow.user_id == user_id))).first():
            flows = (
                await session.exec(
                    select(Flow).where(Flow.name.like(f"{flow.name} (%")).where(Flow.user_id == user_id)  # type: ignore[attr-defined]
                )
            ).all()
            if flows:
                # Use regex to extract numbers only from flows that follow the copy naming pattern:
                # "{original_name} ({number})"
                # This avoids extracting numbers from the original flow name if it naturally contains parentheses
                #
                # Examples:
                # - For flow "My Flow": matches "My Flow (1)", "My Flow (2)" -> extracts 1, 2
                # - For flow "Analytics (Q1)": matches "Analytics (Q1) (1)" -> extracts 1
                #   but does NOT match "Analytics (Q1)" -> avoids extracting the original "1"
                extract_number = re.compile(rf"^{re.escape(flow.name)} \((\d+)\)$")
                numbers = []
                for _flow in flows:
                    result = extract_number.search(_flow.name)
                    if result:
                        numbers.append(int(result.groups(1)[0]))
                if numbers:
                    flow.name = f"{flow.name} ({max(numbers) + 1})"
                else:
                    flow.name = f"{flow.name} (1)"
            else:
                flow.name = f"{flow.name} (1)"

        # Check if the endpoint is unique
        if (
            flow.endpoint_name
            and (
                await session.exec(
                    select(Flow).where(Flow.endpoint_name == flow.endpoint_name).where(Flow.user_id == user_id)
                )
            ).first()
        ):
            if fail_on_endpoint_conflict:
                raise HTTPException(status_code=409, detail="Endpoint name must be unique")

            # Auto-rename endpoint
            flows = (
                await session.exec(
                    select(Flow)
                    .where(Flow.endpoint_name.like(f"{flow.endpoint_name}-%"))  # type: ignore[union-attr]
                    .where(Flow.user_id == user_id)
                )
            ).all()
            if flows:
                # The endpoint name is like "my-endpoint","my-endpoint-1", "my-endpoint-2"
                # so we need to get the highest number and add 1
                numbers = []
                for f in flows:
                    try:
                        numbers.append(int(f.endpoint_name.split("-")[-1]))
                    except ValueError:
                        continue
                next_num = (max(numbers) + 1) if numbers else 1
                flow.endpoint_name = f"{flow.endpoint_name}-{next_num}"
            else:
                flow.endpoint_name = f"{flow.endpoint_name}-1"

        # Exclude the id field from FlowCreate so that Flow.id (UUID, non-optional)
        # always gets its default_factory uuid4 unless we explicitly override it below.
        # Passing id=None via model_validate would cause a Pydantic ValidationError
        # because Flow.id is typed as UUID, not Optional[UUID].
        db_flow = Flow.model_validate(flow.model_dump(exclude={"id"}))

        # Apply the stable ID: the explicit flow_id param (PUT upsert) takes precedence,
        # then flow.id (stable import from FlowCreate), then the uuid4 default.
        effective_id = flow_id if flow_id is not None else flow.id
        if effective_id is not None:
            db_flow.id = effective_id

        db_flow.updated_at = datetime.now(timezone.utc)

        # Validate folder_id exists, or fall back to default folder
        if db_flow.folder_id is not None:
            folder_exists = (
                await session.exec(select(Folder).where(Folder.id == db_flow.folder_id, Folder.user_id == user_id))
            ).first()
            if not folder_exists:
                # Folder doesn't exist or doesn't belong to user, use default
                db_flow.folder_id = None

        if db_flow.folder_id is None:
            # Make sure flows always have a folder (auto-create default folder if needed)
            db_flow.folder_id = await get_default_folder_id(session, user_id)

        session.add(db_flow)

        # Persist and refresh
        await session.flush()
        await session.refresh(db_flow)
        await _save_flow_to_fs(db_flow, user_id, storage_service)

        # Convert to FlowRead while session is still active
        return FlowRead.model_validate(db_flow, from_attributes=True)
    except Exception as e:
        # If it is a validation error, return the error message
        if hasattr(e, "errors"):
            raise HTTPException(status_code=400, detail=str(e)) from e
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _read_flow(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
):
    """Read a flow."""
    stmt = select(Flow).where(Flow.id == flow_id).where(Flow.user_id == user_id)

    return (await session.exec(stmt)).first()


async def _update_existing_flow(
    *,
    session: AsyncSession,
    existing_flow: Flow,
    flow: FlowCreate,
    current_user: User,
    storage_service: StorageService,
) -> FlowRead:
    """Update an existing flow (PUT update path).

    Similar to update_flow but:
    - Fails on name/endpoint_name conflict with OTHER flows (409)
    - Keeps existing folder_id if not provided in request
    """
    settings_service = get_settings_service()
    user_id = current_user.id

    # Validate fs_path if provided (use `is not None` to catch empty strings)
    if flow.fs_path is not None:
        await _verify_fs_path(flow.fs_path, user_id, storage_service)

    # Validate folder_id if provided
    if flow.folder_id is not None:
        folder = (
            await session.exec(select(Folder).where(Folder.id == flow.folder_id, Folder.user_id == user_id))
        ).first()
        if not folder:
            raise HTTPException(status_code=400, detail="Folder not found")

    # Check name uniqueness (excluding current flow)
    if flow.name and flow.name != existing_flow.name:
        name_conflict = (
            await session.exec(
                select(Flow).where(
                    Flow.name == flow.name,
                    Flow.user_id == user_id,
                    Flow.id != existing_flow.id,
                )
            )
        ).first()
        if name_conflict:
            raise HTTPException(status_code=409, detail="Name must be unique")

    # Check endpoint_name uniqueness (excluding current flow)
    if flow.endpoint_name and flow.endpoint_name != existing_flow.endpoint_name:
        endpoint_conflict = (
            await session.exec(
                select(Flow).where(
                    Flow.endpoint_name == flow.endpoint_name,
                    Flow.user_id == user_id,
                    Flow.id != existing_flow.id,
                )
            )
        ).first()
        if endpoint_conflict:
            raise HTTPException(status_code=409, detail="Endpoint name must be unique")

    # Build update data
    update_data = flow.model_dump(exclude_unset=True, exclude_none=True)

    # Preserve the existing endpoint unless the request explicitly clears it.
    if _endpoint_name_was_explicitly_cleared(flow):
        update_data["endpoint_name"] = None

    # Remove id and user_id from update data (security)
    update_data.pop("id", None)
    update_data.pop("user_id", None)

    # If folder_id not provided, keep existing
    if "folder_id" not in update_data or update_data.get("folder_id") is None:
        update_data.pop("folder_id", None)

    if settings_service.settings.remove_api_keys:
        update_data = remove_api_keys(update_data)

    for key, value in update_data.items():
        setattr(existing_flow, key, value)

    webhook_component = get_webhook_component_in_flow(existing_flow.data or {})
    existing_flow.webhook = webhook_component is not None
    existing_flow.updated_at = datetime.now(timezone.utc)

    session.add(existing_flow)
    await session.flush()
    await session.refresh(existing_flow)
    await _save_flow_to_fs(existing_flow, user_id, storage_service)

    return FlowRead.model_validate(existing_flow, from_attributes=True)


async def _patch_flow(
    *,
    session: AsyncSession,
    db_flow: Flow,
    flow: FlowUpdate,
    user_id: UUID,
    storage_service: StorageService,
) -> FlowRead:
    """Apply a partial update (PATCH) to an existing flow and return a FlowRead."""
    settings_service = get_settings_service()

    update_data = flow.model_dump(exclude_unset=True, exclude_none=True)

    # Preserve the existing endpoint unless the request explicitly clears it.
    if _endpoint_name_was_explicitly_cleared(flow):
        update_data["endpoint_name"] = None

    if settings_service.settings.remove_api_keys:
        update_data = remove_api_keys(update_data)

    for key, value in update_data.items():
        setattr(db_flow, key, value)

    # Validate fs_path if it was changed (will raise HTTPException if invalid)
    if "fs_path" in update_data:
        await _verify_fs_path(db_flow.fs_path, user_id, storage_service)

    webhook_component = get_webhook_component_in_flow(db_flow.data) if db_flow.data else None
    db_flow.webhook = webhook_component is not None
    db_flow.updated_at = datetime.now(timezone.utc)

    # Validate folder_id exists, or fall back to default folder
    if db_flow.folder_id is not None:
        folder_exists = (
            await session.exec(select(Folder).where(Folder.id == db_flow.folder_id, Folder.user_id == user_id))
        ).first()
        if not folder_exists:
            db_flow.folder_id = None

    if db_flow.folder_id is None:
        db_flow.folder_id = await get_default_folder_id(session, user_id)

    session.add(db_flow)
    await session.flush()
    await session.refresh(db_flow)
    await _save_flow_to_fs(db_flow, user_id, storage_service)

    return FlowRead.model_validate(db_flow, from_attributes=True)


async def _upsert_flow_list(
    *,
    session: AsyncSession,
    flows: list[FlowCreate],
    current_user: User,
    storage_service: StorageService,
    folder_id: UUID | None = None,
) -> list[FlowRead]:
    """Import a list of flows with upsert semantics (used by the upload endpoint).

    For each flow:
    - If it has an ID matching an existing flow owned by the user, update in place.
    - If it has an ID claimed by another user, mint a fresh UUID.
    - Otherwise create with the provided or generated ID.
    """
    flow_reads: list[FlowRead] = []
    for flow in flows:
        flow.user_id = current_user.id
        if folder_id:
            flow.folder_id = folder_id

        if flow.id is not None:
            existing = (await session.exec(select(Flow).where(Flow.id == flow.id))).first()

            if existing is not None and existing.user_id == current_user.id:
                flow_read = await _update_existing_flow(
                    session=session,
                    existing_flow=existing,
                    flow=flow,
                    current_user=current_user,
                    storage_service=storage_service,
                )
            elif existing is not None:
                flow.id = None
                flow_read = await _new_flow(
                    session=session, flow=flow, user_id=current_user.id, storage_service=storage_service
                )
            else:
                flow_read = await _new_flow(
                    session=session,
                    flow=flow,
                    user_id=current_user.id,
                    storage_service=storage_service,
                    flow_id=flow.id,
                )
        else:
            flow_read = await _new_flow(
                session=session, flow=flow, user_id=current_user.id, storage_service=storage_service
            )

        flow_reads.append(flow_read)
    return flow_reads


def _build_flows_download_response(
    flows: list[Flow],
) -> StreamingResponse | dict:
    """Build a download response (ZIP or single JSON) for the given flows.

    Strips API keys and normalises for git-friendly export before packaging.
    """
    normalised_flows = [normalize_flow_for_export(remove_api_keys(flow.model_dump())) for flow in flows]

    if len(normalised_flows) > 1:
        zip_stream = io.BytesIO()
        with zipfile.ZipFile(zip_stream, "w") as zip_file:
            for flow_dict in normalised_flows:
                flow_json = orjson_dumps(flow_dict, sort_keys=True)
                raw_name = str(flow_dict.get("name", "flow"))
                safe_name = StdlibPath(raw_name).name or str(flow_dict.get("id", "flow"))
                zip_file.writestr(f"{safe_name}.json", flow_json)

        zip_stream.seek(0)
        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_langflow_flows.zip"

        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    return normalised_flows[0]
