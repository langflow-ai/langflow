"""Build a deterministic, secret-scrubbed package from one persisted project."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import stat
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, TypeVar

from sqlmodel import col, select

from langflow.services.authorization import (
    FlowAction,
    ProjectAction,
    ensure_flows_permission,
    ensure_project_permission,
)
from langflow.services.authorization.fetch import authorized_or_owner_scoped
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.folder.model import Folder
from langflow.utils.flow_secrets import strip_secret_field_values_in_place

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead

LFPKG_MEDIA_TYPE = "application/vnd.langflow.lfpkg+zip"

_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_ZIP_FILE_MODE = stat.S_IFREG | 0o644
_MAX_JSON_DEPTH = 128
_MAX_JSON_ITEMS = 500_000
_MAX_ARTIFACT_JSON_ITEMS = 2_000_000
_FLOW_PAGE_SIZE = 4
_ASCII_CONTROL_CUTOFF = 0x20
_UTF8_ONE_BYTE_MAX = 0x7F
_UTF8_TWO_BYTE_MAX = 0x7FF
_UTF8_THREE_BYTE_MAX = 0xFFFF
_UNICODE_SURROGATE_MIN = 0xD800
_UNICODE_SURROGATE_MAX = 0xDFFF
_VOLATILE_TOP_LEVEL_FIELDS = frozenset(
    {"updated_at", "created_at", "user_id", "folder_id", "workspace_id", "access_type", "gradient"}
)
_VOLATILE_NODE_FIELDS = frozenset({"positionAbsolute", "dragging", "selected"})

_T = TypeVar("_T")


class ProjectArtifactError(ValueError):
    """Base class for safe, caller-visible package construction failures."""


class EmptyProjectArtifactError(ProjectArtifactError):
    """Raised when a project has no flows to package."""


class ProjectArtifactNotFoundError(ProjectArtifactError):
    """Raised when the requested project is not visible to the caller."""


class ProjectArtifactLimitError(ProjectArtifactError):
    """Raised when package input exceeds a configured resource ceiling."""


@dataclass(frozen=True, slots=True)
class ProjectArtifactLimits:
    """Resource ceilings applied before returning an in-memory package."""

    max_flow_count: int = 500
    max_flow_bytes: int = 8 * 1024 * 1024
    max_expanded_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        for field_name in ("max_flow_count", "max_flow_bytes", "max_expanded_bytes"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                msg = f"{field_name} must be a positive integer"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ProjectArtifactFlow:
    """Manifest metadata for one packaged flow."""

    flow_id: UUID
    name: str
    path: str
    sha256: str
    size: int
    required_variables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectArtifact:
    """Immutable package bytes and non-secret response metadata."""

    content: bytes
    filename: str
    media_type: str
    project_id: UUID
    project_name: str
    flows: tuple[ProjectArtifactFlow, ...]

    @property
    def flow_count(self) -> int:
        """Return the number of flow payloads in the package."""
        return len(self.flows)


@dataclass(frozen=True, slots=True)
class _FlowSnapshot:
    flow_id: UUID
    name: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _SnapshotBatch:
    snapshots: tuple[_FlowSnapshot, ...]
    estimated_bytes: int
    item_count: int


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=path, date_time=_FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = _ZIP_FILE_MODE << 16
    info.internal_attr = 0
    info.extra = b""
    info.comment = b""
    return info


def _normalized_flow_bytes(snapshot: _FlowSnapshot) -> tuple[bytes, tuple[str, ...]]:
    # Scrubbing and volatile-field removal mutate nested values in place. Copy
    # first so aliases held by the snapshot or persisted Flow data stay intact.
    scrubbed = deepcopy(snapshot.payload)
    # Deployment scrubbing keeps ``load_from_db`` variable-name references so
    # the serving side can provision credentials under the same names; the
    # collected names feed the manifest's required-variables listing.
    variable_references: set[str] = set()
    scrubbed["data"] = strip_secret_field_values_in_place(scrubbed.get("data"), variable_references=variable_references)
    # Deployment packages retain runtime-native code strings. The normal git
    # export path splits code into one list element per line, which is useful
    # for diffs but can amplify a newline-heavy value into millions of Python
    # objects before serialization.
    for key in _VOLATILE_TOP_LEVEL_FIELDS:
        scrubbed.pop(key, None)
    data = scrubbed.get("data")
    if isinstance(data, dict):
        nodes = data.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, dict):
                    for key in _VOLATILE_NODE_FIELDS:
                        node.pop(key, None)
    return _canonical_json_bytes(scrubbed), tuple(sorted(variable_references))


def _json_string_size(value: str) -> int:
    """Return a conservative UTF-8 JSON string size without allocating bytes."""
    total = 2  # surrounding quotes
    for character in value:
        codepoint = ord(character)
        if _UNICODE_SURROGATE_MIN <= codepoint <= _UNICODE_SURROGATE_MAX:
            msg = "project artifact text contains an invalid Unicode surrogate"
            raise ProjectArtifactError(msg)
        if character in {'"', "\\"}:
            total += 2
        elif codepoint < _ASCII_CONTROL_CUTOFF:
            total += 6
        elif codepoint <= _UTF8_ONE_BYTE_MAX:
            total += 1
        elif codepoint <= _UTF8_TWO_BYTE_MAX:
            total += 2
        elif codepoint <= _UTF8_THREE_BYTE_MAX:
            total += 3
        else:
            total += 4
    return total


def _preflight_json_value(
    value: object,
    *,
    flow_id: UUID,
    max_bytes: int,
    max_items: int,
) -> tuple[int, int]:
    """Conservatively bound one JSON-compatible value without serializing it."""
    total_size = 0
    item_count = 0
    # Iterator frames keep traversal memory proportional to nesting depth,
    # rather than allocating one pending tuple per element in a wide list.
    frames: list[tuple[Iterator[object], int]] = [(iter((value,)), 0)]
    while frames:
        values, depth = frames[-1]
        try:
            value = next(values)
        except StopIteration:
            frames.pop()
            continue
        item_count += 1
        if item_count > max_items:
            msg = f"flow file {flow_id} exceeds the {max_items}-item structural limit"
            raise ProjectArtifactLimitError(msg)
        if depth > _MAX_JSON_DEPTH:
            msg = f"flow file {flow_id} exceeds the {_MAX_JSON_DEPTH}-level nesting limit"
            raise ProjectArtifactLimitError(msg)

        if isinstance(value, dict):
            # Braces plus one colon per entry and one comma between entries.
            total_size += 2 + (2 * len(value))
            for key in value:
                total_size += _json_string_size(str(key))
            if value:
                frames.append((iter(value.values()), depth + 1))
        elif isinstance(value, (list, tuple)):
            total_size += 2 + len(value)
            if value:
                frames.append((iter(value), depth + 1))
        elif isinstance(value, str):
            total_size += _json_string_size(value)
        elif value is None or isinstance(value, bool):
            total_size += 5
        elif isinstance(value, (int, float)):
            total_size += len(str(value))
        else:
            msg = f"flow file {flow_id} contains unsupported persisted data"
            raise ProjectArtifactError(msg)

        if total_size > max_bytes:
            msg = f"flow file {flow_id} exceeds the {max_bytes}-byte preflight limit"
            raise ProjectArtifactLimitError(msg)
    return total_size, item_count


def _snapshot_rows(
    rows: tuple[Flow, ...],
    *,
    limits: ProjectArtifactLimits,
    remaining_expanded_bytes: int,
    remaining_items: int,
) -> _SnapshotBatch:
    """Detach and bound one small database page outside the event loop."""
    snapshots: list[_FlowSnapshot] = []
    estimated_bytes = 0
    item_count = 0
    for flow in rows:
        # Bound the persisted graph before Pydantic copies it into a detached
        # payload, then bound the complete exported model against both the
        # per-flow and remaining aggregate budgets.
        _preflight_json_value(
            flow.data,
            flow_id=flow.id,
            max_bytes=limits.max_flow_bytes,
            max_items=_MAX_JSON_ITEMS,
        )
        payload = FlowRead.model_validate(flow, from_attributes=True).model_dump(mode="json")
        flow_size, flow_items = _preflight_json_value(
            payload,
            flow_id=flow.id,
            max_bytes=limits.max_flow_bytes,
            max_items=_MAX_JSON_ITEMS,
        )
        if estimated_bytes + flow_size > remaining_expanded_bytes:
            msg = f"artifact expanded size exceeds the {limits.max_expanded_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)
        if item_count + flow_items > remaining_items:
            msg = f"artifact exceeds the {_MAX_ARTIFACT_JSON_ITEMS}-item structural limit"
            raise ProjectArtifactLimitError(msg)
        estimated_bytes += flow_size
        item_count += flow_items
        snapshots.append(_FlowSnapshot(flow_id=flow.id, name=flow.name, payload=payload))
    return _SnapshotBatch(tuple(snapshots), estimated_bytes, item_count)


def _build_archive(
    *,
    project_id: UUID,
    project_name: str,
    snapshots: tuple[_FlowSnapshot, ...],
    limits: ProjectArtifactLimits,
) -> ProjectArtifact:
    flow_entries: list[ProjectArtifactFlow] = []
    files: list[tuple[str, bytes]] = []
    expanded_size = 0

    # Validate all manifest-only persisted text before serializing any file.
    _json_string_size(project_name)
    for snapshot in snapshots:
        _json_string_size(snapshot.name)

    for snapshot in snapshots:
        path = f"flows/{snapshot.flow_id}.json"
        content, required_variables = _normalized_flow_bytes(snapshot)
        size = len(content)
        if size > limits.max_flow_bytes:
            msg = f"flow file {snapshot.flow_id} is {size} bytes, exceeding the {limits.max_flow_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)
        expanded_size += size
        if expanded_size > limits.max_expanded_bytes:
            msg = f"artifact expanded size exceeds the {limits.max_expanded_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)
        files.append((path, content))
        flow_entries.append(
            ProjectArtifactFlow(
                flow_id=snapshot.flow_id,
                name=snapshot.name,
                path=path,
                sha256=hashlib.sha256(content).hexdigest(),
                size=size,
                required_variables=required_variables,
            )
        )

    manifest = {
        "schema_version": 1,
        "project": {"id": str(project_id), "name": project_name},
        # Names of every load_from_db-bound global variable the packaged flows
        # reference; the deploy target must provision each name before serving.
        "required_variables": sorted({name for flow in flow_entries for name in flow.required_variables}),
        "flows": [
            {
                "id": str(flow.flow_id),
                "name": flow.name,
                "path": flow.path,
                "sha256": flow.sha256,
                "size": flow.size,
                "required_variables": list(flow.required_variables),
            }
            for flow in flow_entries
        ],
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    if len(manifest_bytes) > limits.max_flow_bytes:
        msg = f"manifest file is {len(manifest_bytes)} bytes, exceeding the {limits.max_flow_bytes}-byte limit"
        raise ProjectArtifactLimitError(msg)
    expanded_size += len(manifest_bytes)
    if expanded_size > limits.max_expanded_bytes:
        msg = f"artifact expanded size exceeds the {limits.max_expanded_bytes}-byte limit"
        raise ProjectArtifactLimitError(msg)

    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        archive.writestr(_zip_info("manifest.json"), manifest_bytes)
        for path, content in files:
            archive.writestr(_zip_info(path), content)

    return ProjectArtifact(
        content=output.getvalue(),
        filename=f"langflow-project-{project_id}.lfpkg",
        media_type=LFPKG_MEDIA_TYPE,
        project_id=project_id,
        project_name=project_name,
        flows=tuple(flow_entries),
    )


async def _run_sync_non_abandoning(function: Callable[[], _T]) -> _T:
    """Delay request cancellation until a capacity-accounted worker exits."""
    worker = asyncio.create_task(asyncio.to_thread(function))
    cancellation_requested = False
    while True:
        try:
            result = await asyncio.shield(worker)
            break
        except asyncio.CancelledError:
            cancellation_requested = True
            current_task = asyncio.current_task()
            uncancel = getattr(current_task, "uncancel", None)
            if callable(uncancel):
                uncancel()

    if cancellation_requested:
        raise asyncio.CancelledError
    return result


async def _build_archive_non_abandoning(
    *,
    project_id: UUID,
    project_name: str,
    snapshots: tuple[_FlowSnapshot, ...],
    limits: ProjectArtifactLimits,
) -> ProjectArtifact:
    """Build an archive without outliving its caller's capacity lease."""
    return await _run_sync_non_abandoning(
        partial(
            _build_archive,
            project_id=project_id,
            project_name=project_name,
            snapshots=snapshots,
            limits=limits,
        )
    )


async def build_project_artifact(
    session: AsyncSession,
    user: User | UserRead,
    project_id: UUID,
    *,
    flow_ids: Sequence[UUID] | None = None,
    limits: ProjectArtifactLimits | None = None,
) -> ProjectArtifact:
    """Package selected readable flows, or every flow assigned to the project.

    The project lookup widens beyond the caller's owner namespace only when the
    registered authorization service explicitly supports cross-user fetch. Flow
    membership is determined by project folder regardless of author. Read checks
    are split into an actor-owned batch and a non-owned batch so the owner override
    is never applied to another author's flow, and every check must pass before
    any archive is constructed. Flow authorship and revision are revalidated
    while packaging so either kind of concurrent change fails consistently.
    """
    selected_flow_ids: tuple[UUID, ...] | None = None
    if flow_ids is not None:
        if not flow_ids:
            msg = "flow_ids must contain at least one flow ID when provided"
            raise ProjectArtifactError(msg)
        if len(set(flow_ids)) != len(flow_ids):
            msg = "flow_ids must not contain duplicate flow IDs"
            raise ProjectArtifactError(msg)
        selected_flow_ids = tuple(sorted(flow_ids, key=str))

    project = await authorized_or_owner_scoped(
        session,
        Folder,
        id_column=Folder.id,
        resource_id=project_id,
        owner_column=Folder.user_id,
        owner_id=user.id,
    )
    if project is None:
        msg = "Project not found"
        raise ProjectArtifactNotFoundError(msg)

    await ensure_project_permission(
        user,
        ProjectAction.READ,
        project_id=project_id,
        project_user_id=project.user_id,
        workspace_id=project.workspace_id,
    )

    effective_limits = limits or ProjectArtifactLimits()
    if selected_flow_ids is not None and len(selected_flow_ids) > effective_limits.max_flow_count:
        msg = f"selected flow count {len(selected_flow_ids)} exceeds the {effective_limits.max_flow_count}-flow limit"
        raise ProjectArtifactLimitError(msg)
    revision_statement = select(Flow.id, Flow.user_id, Flow.updated_at).where(Flow.folder_id == project_id)
    if selected_flow_ids is not None:
        revision_statement = revision_statement.where(col(Flow.id).in_(selected_flow_ids))
    revision_rows = list(
        (await session.exec(revision_statement.order_by(col(Flow.id)).limit(effective_limits.max_flow_count + 1))).all()
    )
    if selected_flow_ids is not None and len(revision_rows) != len(selected_flow_ids):
        msg = "one or more selected flows were not found in the project"
        raise ProjectArtifactNotFoundError(msg)
    if not revision_rows:
        msg = "project has no flows to package"
        raise EmptyProjectArtifactError(msg)
    if len(revision_rows) > effective_limits.max_flow_count:
        msg = f"project flow count {len(revision_rows)} exceeds the {effective_limits.max_flow_count}-flow limit"
        raise ProjectArtifactLimitError(msg)

    ordered_revisions = tuple(sorted(revision_rows, key=lambda revision: str(revision[0])))
    ordered_flow_ids = tuple(flow_id for flow_id, _flow_user_id, _updated_at in ordered_revisions)
    initial_revisions = {flow_id: (flow_user_id, updated_at) for flow_id, flow_user_id, updated_at in ordered_revisions}
    actor_owned_flow_ids = [
        flow_id for flow_id, flow_user_id, _updated_at in ordered_revisions if flow_user_id == user.id
    ]
    non_owned_flow_ids = [
        flow_id for flow_id, flow_user_id, _updated_at in ordered_revisions if flow_user_id != user.id
    ]
    for permission_flow_ids, flow_user_id in (
        (actor_owned_flow_ids, user.id),
        (non_owned_flow_ids, None),
    ):
        if permission_flow_ids:
            await ensure_flows_permission(
                user,
                FlowAction.READ,
                flow_ids=permission_flow_ids,
                flow_user_id=flow_user_id,
                workspace_id=project.workspace_id,
                folder_id=project_id,
            )

    snapshots: list[_FlowSnapshot] = []
    estimated_bytes = 0
    item_count = 0
    for page_start in range(0, len(ordered_flow_ids), _FLOW_PAGE_SIZE):
        page_ids = ordered_flow_ids[page_start : page_start + _FLOW_PAGE_SIZE]
        rows = list(
            (
                await session.exec(
                    select(Flow)
                    .where(
                        col(Flow.id).in_(page_ids),
                        Flow.folder_id == project_id,
                    )
                    .order_by(col(Flow.id))
                )
            ).all()
        )
        ordered_rows = tuple(sorted(rows, key=lambda flow: str(flow.id)))
        expected_page_revisions = tuple((flow_id, *initial_revisions[flow_id]) for flow_id in page_ids)
        if tuple((flow.id, flow.user_id, flow.updated_at) for flow in ordered_rows) != expected_page_revisions:
            msg = "project flows changed during packaging"
            raise ProjectArtifactError(msg)

        remaining_expanded_bytes = effective_limits.max_expanded_bytes - estimated_bytes
        remaining_items = _MAX_ARTIFACT_JSON_ITEMS - item_count
        if remaining_expanded_bytes <= 0:
            msg = f"artifact expanded size exceeds the {effective_limits.max_expanded_bytes}-byte limit"
            raise ProjectArtifactLimitError(msg)
        if remaining_items <= 0:
            msg = f"artifact exceeds the {_MAX_ARTIFACT_JSON_ITEMS}-item structural limit"
            raise ProjectArtifactLimitError(msg)
        batch = await _run_sync_non_abandoning(
            partial(
                _snapshot_rows,
                ordered_rows,
                limits=effective_limits,
                remaining_expanded_bytes=remaining_expanded_bytes,
                remaining_items=remaining_items,
            )
        )
        snapshots.extend(batch.snapshots)
        estimated_bytes += batch.estimated_bytes
        item_count += batch.item_count

    final_revision_statement = select(Flow.id, Flow.user_id, Flow.updated_at).where(Flow.folder_id == project_id)
    if selected_flow_ids is not None:
        final_revision_statement = final_revision_statement.where(col(Flow.id).in_(selected_flow_ids))
    final_revisions = tuple(
        (
            await session.exec(
                final_revision_statement.order_by(col(Flow.id)).limit(effective_limits.max_flow_count + 1)
            )
        ).all()
    )
    if final_revisions != ordered_revisions:
        msg = "project flows changed during packaging"
        raise ProjectArtifactError(msg)

    # Archive construction is intentionally non-abandoning. If the HTTP request
    # is cancelled, keep the caller suspended until the worker exits so the
    # Enterprise package semaphore continues to account for its memory use.
    return await _build_archive_non_abandoning(
        project_id=project_id,
        project_name=project.name,
        snapshots=tuple(snapshots),
        limits=effective_limits,
    )
