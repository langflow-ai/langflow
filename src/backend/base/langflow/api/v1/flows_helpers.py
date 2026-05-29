"""Helper functions for flow CRUD and filesystem operations.

Extracted from flows.py to keep the route-handler module concise.
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

import aiofiles
from anyio import Path
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from lfx.log import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import build_content_disposition, normalize_flow_for_export, remove_api_keys
from langflow.services.database.models.base import orjson_dumps
from langflow.services.database.models.deployment.orm_guards import ensure_flow_move_allowed
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

    Uses ``os.path.realpath`` + ``startswith`` for containment — the sanitiser pattern
    recognised by CodeQL's ``py/path-injection`` analysis. ``realpath`` canonicalises
    the path and follows symlinks, so the returned path is safe to pass to filesystem
    operations.
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

    # Build and canonicalise the safe base directory path.
    base_dir = storage_service.data_dir / "flows" / str(user_id)
    try:
        base_dir_resolved = os.path.realpath(str(base_dir))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid base directory: {e}") from e

    # Determine if path is absolute (Unix or Windows style)
    is_absolute = normalized_path.startswith("/") or (len(normalized_path) > 1 and normalized_path[1] == ":")

    if is_absolute:
        candidate = normalized_path
    else:
        relative_part = normalized_path.lstrip("/")
        # os.path.join is deliberate here (PTH118) to match CodeQL's sanitiser model.
        candidate = os.path.join(base_dir_resolved, relative_part) if relative_part else base_dir_resolved  # noqa: PTH118

    try:
        resolved_str = os.path.realpath(candidate)
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}") from e

    # SECURITY: containment check using os.path.realpath + startswith (CodeQL-recognised).
    if resolved_str != base_dir_resolved and not resolved_str.startswith(base_dir_resolved + os.sep):
        if is_absolute:
            raise HTTPException(
                status_code=400,
                detail="Absolute path must be within your flows directory",
            )
        raise HTTPException(
            status_code=400,
            detail="Invalid path: resolves outside allowed directory",
        )

    # Return the canonicalised path — safe for subsequent filesystem operations.
    return Path(resolved_str)


# Fields that may be updated via setattr on a Flow ORM instance.
# Any key not in this set is silently dropped to prevent callers from
# overwriting internal fields (e.g. ``id``, ``user_id``).
_UPDATABLE_FLOW_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "description",
        "data",
        "is_component",
        "endpoint_name",
        "tags",
        "folder_id",
        # ``workspace_id`` is part of the FlowUpdate / FlowCreate contract and
        # the PATCH/PUT routes re-authorize WRITE at the destination scope when
        # the payload changes it (see flows.py). Omitting it here would silently
        # accept the payload, pass the authorization check, and then drop the
        # write — leaving the flow in its old workspace despite the API saying
        # the move succeeded.
        "workspace_id",
        "icon",
        "icon_bg_color",
        "gradient",
        "locked",
        "mcp_enabled",
        "action_name",
        "action_description",
        "access_type",
        "fs_path",
    }
)


def _apply_update_data(target: Flow, update_data: dict[str, Any]) -> None:
    """Apply *update_data* to the ORM *target*, restricted to the allowlist."""
    for key, value in update_data.items():
        if key in _UPDATABLE_FLOW_FIELDS:
            setattr(target, key, value)


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
        async with aiofiles.open(str(safe_path), "w") as f:
            await f.write(flow.model_dump_json())
    except HTTPException:
        raise
    except OSError as e:
        await logger.aexception("Failed to write flow %s to path %s", flow.name, flow.fs_path)
        raise HTTPException(status_code=500, detail=f"Failed to write flow to filesystem: {e}") from e


async def _deduplicate_flow_name(session: AsyncSession, name: str, user_id: UUID) -> str:
    """Return a unique flow name for *user_id*, appending ``(N)`` if needed."""
    if not (await session.exec(select(Flow).where(Flow.name == name).where(Flow.user_id == user_id))).first():
        return name

    flows = (
        await session.exec(
            select(Flow).where(Flow.name.like(f"{name} (%")).where(Flow.user_id == user_id)  # type: ignore[attr-defined]
        )
    ).all()

    # Extract copy-number suffixes: "MyFlow (2)" → 2
    extract_number = re.compile(rf"^{re.escape(name)} \((\d+)\)$")
    numbers = [int(m.group(1)) for f in flows if (m := extract_number.search(f.name))]

    return f"{name} ({max(numbers) + 1})" if numbers else f"{name} (1)"


async def _deduplicate_endpoint_name(
    session: AsyncSession,
    endpoint_name: str,
    user_id: UUID,
    *,
    fail_on_conflict: bool = False,
) -> str:
    """Return a unique endpoint name for *user_id*, appending ``-N`` if needed.

    Raises :class:`HTTPException` 409 when *fail_on_conflict* is ``True`` and
    the name already exists.
    """
    existing = (
        await session.exec(select(Flow).where(Flow.endpoint_name == endpoint_name).where(Flow.user_id == user_id))
    ).first()
    if not existing:
        return endpoint_name

    if fail_on_conflict:
        raise HTTPException(status_code=409, detail="Endpoint name must be unique")

    flows = (
        await session.exec(
            select(Flow)
            .where(Flow.endpoint_name.like(f"{endpoint_name}-%"))  # type: ignore[union-attr]
            .where(Flow.user_id == user_id)
        )
    ).all()

    numbers: list[int] = []
    for f in flows:
        try:
            numbers.append(int(f.endpoint_name.split("-")[-1]))
        except ValueError:
            continue

    next_num = (max(numbers) + 1) if numbers else 1
    return f"{endpoint_name}-{next_num}"


async def _validate_and_assign_folder(
    session: AsyncSession,
    db_flow: Flow,
    user_id: UUID,
) -> None:
    """Ensure *db_flow* has a valid ``folder_id`` belonging to *user_id*.

    Falls back to the default folder when the current ``folder_id`` is
    ``None`` or references a non-existent / other-user's folder.
    """
    old_folder_id = db_flow.folder_id
    # no_autoflush prevents the guard query (ensure_flow_move_allowed)
    # from flushing the in-progress folder_id mutation before the guard
    # has validated it.
    with session.no_autoflush:
        if db_flow.folder_id is not None:
            folder_exists = (
                await session.exec(select(Folder).where(Folder.id == db_flow.folder_id, Folder.user_id == user_id))
            ).first()
            if not folder_exists:
                db_flow.folder_id = None

        if db_flow.folder_id is None:
            db_flow.folder_id = await get_default_folder_id(session, user_id)

        await ensure_flow_move_allowed(
            session,
            flow_id=db_flow.id,
            old_folder_id=old_folder_id,
            new_folder_id=db_flow.folder_id,
        )


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
        await _verify_fs_path(flow.fs_path, user_id, storage_service)

        if validate_folder and flow.folder_id is not None:
            folder = (
                await session.exec(select(Folder).where(Folder.id == flow.folder_id, Folder.user_id == user_id))
            ).first()
            if not folder:
                raise HTTPException(status_code=400, detail="Folder not found")

        # Set user_id (ignore any user_id from body for security)
        flow.user_id = user_id
        flow.name = await _deduplicate_flow_name(session, flow.name, user_id)

        if flow.endpoint_name:
            flow.endpoint_name = await _deduplicate_endpoint_name(
                session, flow.endpoint_name, user_id, fail_on_conflict=fail_on_endpoint_conflict
            )

        # Exclude the id field from FlowCreate so that Flow.id (UUID, non-optional)
        # always gets its default_factory uuid4 unless we explicitly override it below.
        db_flow = Flow.model_validate(flow.model_dump(exclude={"id"}))

        # Apply the stable ID: explicit flow_id param (PUT upsert) takes precedence,
        # then flow.id (stable import from FlowCreate), then the uuid4 default.
        effective_id = flow_id if flow_id is not None else flow.id
        if effective_id is not None:
            db_flow.id = effective_id

        db_flow.updated_at = datetime.now(timezone.utc)
        await _validate_and_assign_folder(session, db_flow, user_id)

        session.add(db_flow)
        await session.flush()
        await session.refresh(db_flow)
        await _save_flow_to_fs(db_flow, user_id, storage_service)

        return FlowRead.model_validate(db_flow, from_attributes=True)
    except Exception as e:
        if hasattr(e, "errors"):
            raise HTTPException(status_code=400, detail=str(e)) from e
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error creating flow")
        raise HTTPException(status_code=500, detail="An internal error occurred while creating the flow.") from e


async def _read_flow(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
):
    """Read a flow.

    When the registered authorization service supports cross-user fetch
    (authorization plugin), the row is loaded by id alone and the caller's
    ``ensure_flow_permission`` decides access. Otherwise the query stays
    owner-scoped so the OSS pass-through default cannot widen visibility.
    """
    from langflow.services.authorization.fetch import authorized_or_owner_scoped

    return await authorized_or_owner_scoped(
        session,
        Flow,
        id_column=Flow.id,
        resource_id=flow_id,
        owner_column=Flow.user_id,
        owner_id=user_id,
    )


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

    ``current_user`` is the *actor* (the API caller). The flow's owner is
    ``existing_flow.user_id``. When the actor is not the owner — a cross-user
    shared edit allowed by a registered authorization plugin — ownership-
    bound state (folder, fs_path, ownership) must stay rooted at the owner,
    otherwise the write silently retargets folders/storage that belong to the
    actor. This mirrors the cross-user semantics already enforced by
    ``_patch_flow``.
    """
    settings_service = get_settings_service()
    actor_user_id = current_user.id
    owner_user_id: UUID = existing_flow.user_id
    is_owner_edit = owner_user_id == actor_user_id

    # Non-owner edits cannot relocate the flow into folders or storage they
    # own, nor transfer ownership. Reject early so the failure is explicit
    # rather than corrupting scope downstream.
    if not is_owner_edit:
        if flow.folder_id is not None and flow.folder_id != existing_flow.folder_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot change folder of a flow you do not own.",
            )
        if flow.fs_path is not None and flow.fs_path != existing_flow.fs_path:
            raise HTTPException(
                status_code=403,
                detail="Cannot change fs_path of a flow you do not own.",
            )
        if flow.user_id is not None and flow.user_id != owner_user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot transfer ownership of a flow you do not own.",
            )

    # Validate fs_path if provided (use `is not None` to catch empty strings).
    # Path safety is scoped to the *owner* — fs_path lives under the owner's
    # storage namespace, so we must not authorize it against the actor's.
    if flow.fs_path is not None:
        await _verify_fs_path(flow.fs_path, owner_user_id, storage_service)

    # Validate folder_id if provided — scoped to the owner so a non-owner
    # cannot land the flow in their own default folder via this code path.
    if flow.folder_id is not None:
        folder = (
            await session.exec(select(Folder).where(Folder.id == flow.folder_id, Folder.user_id == owner_user_id))
        ).first()
        if not folder:
            raise HTTPException(status_code=400, detail="Folder not found")

    # Check name uniqueness against the *owner's* flows (the unique constraint
    # is (user_id, name); checking against the actor's namespace would miss
    # collisions when actor != owner).
    if flow.name and flow.name != existing_flow.name:
        name_conflict = (
            await session.exec(
                select(Flow).where(
                    Flow.name == flow.name,
                    Flow.user_id == owner_user_id,
                    Flow.id != existing_flow.id,
                )
            )
        ).first()
        if name_conflict:
            raise HTTPException(status_code=409, detail="Name must be unique")

    # Check endpoint_name uniqueness — same owner-scope rationale.
    if flow.endpoint_name and flow.endpoint_name != existing_flow.endpoint_name:
        endpoint_conflict = (
            await session.exec(
                select(Flow).where(
                    Flow.endpoint_name == flow.endpoint_name,
                    Flow.user_id == owner_user_id,
                    Flow.id != existing_flow.id,
                )
            )
        ).first()
        if endpoint_conflict:
            raise HTTPException(status_code=409, detail="Endpoint name must be unique")

    # None-valued inputs are treated as omitted by default for updates.
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
    elif update_data["folder_id"] != existing_flow.folder_id:
        await ensure_flow_move_allowed(
            session,
            flow_id=existing_flow.id,
            old_folder_id=existing_flow.folder_id,
            new_folder_id=update_data["folder_id"],
        )

    if settings_service.settings.remove_api_keys:
        update_data = remove_api_keys(update_data)

    _apply_update_data(existing_flow, update_data)

    webhook_component = get_webhook_component_in_flow(existing_flow.data or {})
    existing_flow.webhook = webhook_component is not None
    existing_flow.updated_at = datetime.now(timezone.utc)

    session.add(existing_flow)
    await session.flush()
    await session.refresh(existing_flow)
    # Writes happen under the owner's storage namespace, not the actor's.
    await _save_flow_to_fs(existing_flow, owner_user_id, storage_service)

    return FlowRead.model_validate(existing_flow, from_attributes=True)


async def _patch_flow(
    *,
    session: AsyncSession,
    db_flow: Flow,
    flow: FlowUpdate,
    user_id: UUID,
    storage_service: StorageService,
) -> FlowRead:
    """Apply a partial update (PATCH) to an existing flow and return a FlowRead.

    ``user_id`` is the *actor* — the caller making the patch. The flow's
    owner is ``db_flow.user_id``. For shared edits (actor != owner) we keep
    folder/fs operations rooted at the owner so a non-owner write does not
    silently move the flow into the actor's folder or write into the actor's
    fs namespace; the actor cannot change ownership-bound state at all.
    """
    settings_service = get_settings_service()

    owner_user_id: UUID = db_flow.user_id
    is_owner_edit = owner_user_id == user_id

    # PATCH follows the same rule: None-valued fields are omitted unless
    # explicitly reintroduced below (for example endpoint_name clear).
    update_data = flow.model_dump(exclude_unset=True, exclude_none=True)

    # Preserve the existing endpoint unless the request explicitly clears it.
    if _endpoint_name_was_explicitly_cleared(flow):
        update_data["endpoint_name"] = None

    # A non-owner editing a shared flow must not be able to relocate the
    # flow into folders or storage they own. Reject ownership-bound mutations
    # explicitly so the failure surfaces in the response instead of silently
    # corrupting scope inside ``_validate_and_assign_folder``.
    if not is_owner_edit:
        if "folder_id" in update_data and update_data["folder_id"] != db_flow.folder_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot change folder of a flow you do not own.",
            )
        if "fs_path" in update_data and update_data["fs_path"] != db_flow.fs_path:
            raise HTTPException(
                status_code=403,
                detail="Cannot change fs_path of a flow you do not own.",
            )
        if "user_id" in update_data and update_data["user_id"] != owner_user_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot transfer ownership of a flow you do not own.",
            )

    if "folder_id" in update_data and update_data["folder_id"] != db_flow.folder_id:
        await ensure_flow_move_allowed(
            session,
            flow_id=db_flow.id,
            old_folder_id=db_flow.folder_id,
            new_folder_id=update_data["folder_id"],
        )

    if settings_service.settings.remove_api_keys:
        update_data = remove_api_keys(update_data)

    _apply_update_data(db_flow, update_data)

    # Validate fs_path if it was changed (will raise HTTPException if invalid).
    # fs_path lives under the owner's storage namespace, so the owner id
    # gates the safe-path check.
    if "fs_path" in update_data:
        await _verify_fs_path(db_flow.fs_path, owner_user_id, storage_service)

    webhook_component = get_webhook_component_in_flow(db_flow.data) if db_flow.data else None
    db_flow.webhook = webhook_component is not None
    db_flow.updated_at = datetime.now(timezone.utc)

    # Folder validation must be scoped to the owner — otherwise a non-owner
    # edit would land in the actor's default folder (see ``_validate_and_assign_folder``).
    await _validate_and_assign_folder(session, db_flow, owner_user_id)

    session.add(db_flow)
    await session.flush()
    await session.refresh(db_flow)
    # Writes happen under the owner's storage namespace, not the actor's.
    await _save_flow_to_fs(db_flow, owner_user_id, storage_service)

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


def _sanitize_flow_filename(raw_name: str, fallback_id: str = "flow") -> str:
    """Return a filesystem-safe filename from a flow name.

    Strips directory separators, null bytes, and Windows reserved device names.
    """
    name = str(raw_name).replace("/", "_").replace("\\", "_")
    name = name.replace("\x00", "").replace("..", "_").strip()
    # Reject Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    import re as _re

    if _re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..+)?$", name, _re.IGNORECASE):
        name = f"_{name}"
    return name or fallback_id


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
                safe_name = _sanitize_flow_filename(raw_name, str(flow_dict.get("id", "flow")))
                zip_file.writestr(f"{safe_name}.json", flow_json)

        zip_stream.seek(0)
        current_time = datetime.now(tz=timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_time}_langflow_flows.zip"

        cd = build_content_disposition(filename)
        return StreamingResponse(
            zip_stream,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": cd},
        )
    return normalised_flows[0]
