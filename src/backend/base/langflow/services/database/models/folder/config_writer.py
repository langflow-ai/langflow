"""Apply project configuration to the selected flow in the project's save transaction."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.projects import DEFAULT_PROJECT_TYPE, apply_project_config, get_project_type
from lfx.projects.bindings import (
    compose_instructions,
)
from lfx.projects.compaction import compose_compaction
from lfx.projects.context import compose_context
from lfx.projects.hooks import compose_hooks
from lfx.projects.permissions import compose_permission
from lfx.projects.skills import compose_skills
from lfx.projects.tools import agent_node_ids, compose_tools
from sqlmodel import col, select

from langflow.services.database.models.flow.guards import LockedFlowError, ensure_flow_unlocked
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.references import validate_project_references

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

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
    """Dispatch to lifecycle hooks; harness migration is isolated until E05/E06."""
    try:
        definition = get_project_type(project.project_type or DEFAULT_PROJECT_TYPE)
    except ValueError as exc:
        raise HTTPException(
            422, "The project type plugin is unavailable. Restore it before saving configuration."
        ) from exc
    if definition.name != "agent-harness":
        from langflow.services.database.models.folder.save_hooks import write_with_hooks

        return await write_with_hooks(
            session, project, definition, current_user=current_user, previous_config=previous_config, creating=creating
        )
    return await _write_harness_config(session, project, current_user=current_user, previous_config=previous_config)


async def _write_harness_config(
    session: AsyncSession, project: Folder, *, current_user: User, previous_config: dict | None = None
) -> ProjectConfigWrite:
    from lfx.projects.lifecycle import FlowSelector, ProjectConfigError, SaveRequest

    from langflow.services.database.models.folder.save_context import (
        LangflowProjectSaveContext,
        project_error_http,
        public_config,
    )

    result = ProjectConfigWrite()
    clearing_config = project.project_config is None
    project_type = get_project_type(project.project_type or DEFAULT_PROJECT_TYPE)
    ctx = LangflowProjectSaveContext(session, current_user)
    identity = await ctx.start_save(project)
    flows = list(
        (
            await session.exec(
                select(Flow).where(Flow.folder_id == project.id, Flow.user_id == project.user_id).order_by(Flow.id)
            )
        ).all()
    )
    try:
        views = tuple([await ctx.read_flow(FlowSelector(id=flow.id), access="read") for flow in flows])
        await validate_project_references(session, current_user, project_type, project.project_config or {})
        prepared = await project_type.save_config(
            SaveRequest(
                identity,
                "clear" if clearing_config else "replace",
                public_config(project.project_config),
                public_config(previous_config),
                views,
            ),
            ctx,
        )
        await ctx.verify_unchanged()
        targets = [await ctx.writable_target(flow_id, project) for flow_id in prepared.target_flow_ids]
    except ProjectConfigError as exc:
        raise project_error_http(exc) from exc
    if prepared.state is None:
        return result
    state = prepared.state
    config = deepcopy(state.config)
    config["_applied"] = deepcopy((previous_config or {}).get("_applied", {}))
    bindings, skills = state.bindings, state.skills
    instruction_binding, instruction_target = bindings.system_prompt, state.instruction_target
    local_targets, pack_targets = list(state.tool_targets), []
    applied = config.get("_applied", {})
    applied = deepcopy(applied) if isinstance(applied, dict) else {}
    if previous_config and "_applied" not in previous_config:
        # The legacy writer targeted every flow. Keep all those baselines before
        # replacing the old config, including locked flows and future agent choices.
        for flow in flows:
            applied.setdefault(
                str(flow.id), apply_project_config(flow.data, project_type, previous_config).applied_values
            )
    for flow in targets:
        flow_id = str(flow.id)
        try:
            ensure_flow_unlocked(flow)
        except LockedFlowError:
            result.flows_locked += 1
            continue
        values = {key: value for key, value in config.items() if key != "system_prompt" or instruction_binding is None}
        write = apply_project_config(flow.data, project_type, values, previous_values=applied.get(flow_id))
        result.fields_skipped += write.inputs_skipped
        applied[flow_id] = write.applied_values
        data = write.data
        if project_type.name == "agent-harness":
            try:
                data = compose_skills(data, project_id=str(project.id), agent_id=agent_node_ids(data)[0], skills=skills)
            except (ValueError, TypeError) as exc:
                raise HTTPException(422, f"Could not configure skills: {exc}") from exc
            try:
                data = compose_instructions(
                    data,
                    project_id=str(project.id),
                    agent_id=agent_node_ids(data)[0],
                    target={"name": instruction_target.name, "data": instruction_target.data}
                    if instruction_target
                    else None,
                    binding=instruction_binding,
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, f"Could not bind Instructions: {exc}") from exc
            try:
                data = compose_hooks(
                    data, project_id=str(project.id), agent_id=agent_node_ids(data)[0], bindings=bindings.hooks
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, f"Could not bind Hooks: {exc}") from exc
            try:
                data = compose_context(
                    data,
                    project_id=str(project.id),
                    agent_id=agent_node_ids(data)[0],
                    binding=bindings.context_strategy,
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, f"Could not bind Context: {exc}") from exc
            try:
                data = compose_compaction(
                    data,
                    project_id=str(project.id),
                    agent_id=agent_node_ids(data)[0],
                    binding=bindings.compaction,
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, f"Could not bind Compaction: {exc}") from exc
            try:
                data = compose_permission(
                    data,
                    project_id=str(project.id),
                    agent_id=agent_node_ids(data)[0],
                    binding=bindings.tool_policy,
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, f"Could not bind Permissions: {exc}") from exc
        if project_type.name == "agent-harness" and (
            "tools" in config
            or "tool_packs" in config
            or "skill_packs" in config
            or (previous_config or {}).get("tool_packs")
            or (previous_config or {}).get("skill_packs")
            or clearing_config
        ):
            try:
                data = compose_tools(
                    data,
                    project_id=str(project.id),
                    agent_id=agent_node_ids(data)[0],
                    targets=local_targets + pack_targets,
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, f"Could not configure the selected tools: {exc}") from exc
        if data == flow.data:
            continue
        version_id = await _restore_point(session, flow)
        if version_id:
            result.restore_version_ids[flow_id] = version_id
        flow.data = data
        flow.updated_at = datetime.now(timezone.utc)
        session.add(flow)
        result.flows.append(flow)

    config["_applied"] = applied
    project.project_config = None if clearing_config else config
    session.add(project)
    return result
