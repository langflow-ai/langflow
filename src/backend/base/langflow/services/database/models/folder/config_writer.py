"""Apply project configuration to the selected flow in the project's save transaction."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.projects import DEFAULT_PROJECT_TYPE, get_project_type
from sqlmodel import col, select

from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.model import FlowVersion

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.user.model import User


@dataclass
class ProjectConfigWrite:
    flows: list[Flow] = field(default_factory=list)
    fields_skipped: int = 0
    flows_locked: int = 0
    restore_version_ids: dict[str, str] = field(default_factory=dict)


def config_from_request(incoming: dict | None, previous: dict | None = None) -> dict | None:
    """The form owns values; only the server updates its last-applied baseline."""
    if incoming is None:
        return None
    config = deepcopy(incoming)
    config.pop("_applied", None)
    if previous and isinstance(previous.get("_applied"), dict):
        config["_applied"] = deepcopy(previous["_applied"])
    return config


async def _restore_point(session: AsyncSession, flow: Flow) -> str | None:
    """A deduplicated, best-effort version in the same transaction as the project save."""
    if flow.user_id is None or not flow.data:
        return None
    try:
        async with session.begin_nested():
            latest = (
                await session.exec(
                    select(FlowVersion)
                    .where(FlowVersion.flow_id == flow.id, FlowVersion.user_id == flow.user_id)
                    .order_by(col(FlowVersion.version_number).desc())
                    .limit(1)
                )
            ).first()
            if latest is not None and latest.data == flow.data:
                return str(latest.id)
            entry = await create_flow_version_entry(
                session,
                flow.id,
                flow.user_id,
                data=deepcopy(flow.data),
                description="Before harness configuration save",
            )
            return str(entry.id)
    except Exception:  # noqa: BLE001 — versioning is best effort; the savepoint isolates failures
        await logger.awarning("Could not create a harness restore point for flow %s", flow.id)
        return None


async def write_project_config_to_flows(
    session: AsyncSession,
    project: Folder,
    *,
    current_user: User,
    previous_config: dict | None = None,
    creating: bool = False,
) -> ProjectConfigWrite:
    """Prepare and compose every registered type through the same host transaction."""
    try:
        definition = get_project_type(project.project_type or DEFAULT_PROJECT_TYPE)
    except ValueError as exc:
        raise HTTPException(
            422, "The project type plugin is unavailable. Restore it before saving configuration."
        ) from exc
    from langflow.services.database.models.folder.save_hooks import write_with_hooks

    return await write_with_hooks(
        session, project, definition, current_user=current_user, previous_config=previous_config, creating=creating
    )
