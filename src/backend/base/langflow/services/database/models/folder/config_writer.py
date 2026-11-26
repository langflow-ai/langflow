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
    FlowBinding,
    compose_instructions,
    reject_recursive_binding,
    validate_instruction_binding,
)
from lfx.projects.tools import agent_node_ids, compose_tools
from sqlmodel import col, select

from langflow.services.database.models.flow.guards import LockedFlowError, ensure_flow_unlocked
from langflow.services.database.models.flow.model import Flow, FlowType
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.model import FlowVersion

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.folder.model import Folder


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


def select_agent_flow(flows: list[Flow], config: dict) -> Flow | None:
    """Prefer an explicit selection, then a unique marked agent, then a unique graph candidate.

    A2A owns ``flow_type``. Harness selection is saved in the existing project config, so
    choosing an entry flow never reclassifies another flow or changes A2A publication.
    """
    candidates = [flow for flow in flows if len(agent_node_ids(flow.data)) == 1 and not flow.is_component]
    selected = config.get("agent_flow_id")
    if selected is not None:
        for flow in candidates:
            if str(flow.id) == selected:
                return flow
        raise HTTPException(422, "Choose an agent flow in this project containing exactly one Agent component.")
    marked = [flow for flow in candidates if flow.flow_type == FlowType.AGENT]
    choices = marked or candidates
    if len(choices) > 1 or (not choices and any(agent_node_ids(flow.data) for flow in flows)):
        raise HTTPException(422, "Choose which flow is the agent before saving the harness.")
    return choices[0] if choices else None


def selected_tools(flows: list[Flow], agent: Flow | None, value: object) -> list[Flow]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise HTTPException(422, "Tools must be a list of flow IDs from this project.")
    available = {str(flow.id): flow for flow in flows if not flow.is_component}
    picked = []
    for flow_id in dict.fromkeys(value):
        if flow_id not in available:
            raise HTTPException(422, "A selected tool is no longer available in this project.")
        if agent is None:
            raise HTTPException(422, "Choose an agent flow before adding tools.")
        if flow_id == str(agent.id):
            raise HTTPException(422, "The agent flow cannot call itself as a tool.")
        picked.append(available[flow_id])

    # Refuse a tool that calls back into this agent through other local Run Flow nodes.
    by_name = {flow.name: str(flow.id) for flow in flows}
    pending = [str(flow.id) for flow in picked]
    seen = set()
    while pending:
        current = pending.pop()
        if agent is not None and current == str(agent.id):
            raise HTTPException(422, "A selected tool calls back into the agent flow.")
        if current in seen or current not in available:
            continue
        seen.add(current)
        for node in (available[current].data or {}).get("nodes", []):
            data = node.get("data", {})
            if data.get("type") != "RunFlow":
                continue
            template = data.get("node", {}).get("template", {})
            target = template.get("flow_id_selected", {}).get("value") or by_name.get(
                template.get("flow_name_selected", {}).get("value")
            )
            if isinstance(target, str):
                pending.append(target)
    return picked


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
    session: AsyncSession, project: Folder, *, previous_config: dict | None = None
) -> ProjectConfigWrite:
    result = ProjectConfigWrite()
    clearing_config = project.project_config is None
    if not project.project_config and not (previous_config or {}).get("flow_bindings"):
        return result
    try:
        project_type = get_project_type(project.project_type or DEFAULT_PROJECT_TYPE)
    except ValueError:
        await logger.awarning(
            "Project %s has unknown project_type %r; not writing through.", project.id, project.project_type
        )
        return result
    if not project_type.fields:
        return result

    flows = list(
        (
            await session.exec(
                select(Flow).where(Flow.folder_id == project.id, Flow.user_id == project.user_id).with_for_update()
            )
        ).all()
    )
    config = deepcopy(project.project_config or {})
    if not project.project_config and previous_config:
        # Clearing configuration still removes its generated Instructions connection.
        config["agent_flow_id"] = previous_config.get("agent_flow_id")
    targets = flows
    tools = []
    instruction_target = None
    instruction_binding = None
    if project_type.name == "agent-harness":
        agent = select_agent_flow(flows, config)
        targets = [agent] if agent else []
        if "tools" in config:
            tools = selected_tools(flows, agent, config["tools"])
        if agent is not None:
            config["agent_flow_id"] = str(agent.id)
        bindings = config.get("flow_bindings", {})
        if not isinstance(bindings, dict) or set(bindings) - {"system_prompt"}:
            raise HTTPException(422, "Only Instructions currently supports a flow binding.")
        if "system_prompt" in bindings:
            try:
                instruction_binding = FlowBinding.model_validate(bindings["system_prompt"])
                instruction_target = next(
                    (flow for flow in flows if str(flow.id) == instruction_binding.flow_id and not flow.is_component),
                    None,
                )
                if instruction_target is None or agent is None:
                    msg = "Choose an agent and an Instructions flow in this project."
                    raise ValueError(msg)
                reject_recursive_binding(
                    [{"id": str(flow.id), "name": flow.name, "data": flow.data} for flow in flows],
                    str(instruction_target.id),
                    str(agent.id),
                )
                validate_instruction_binding(instruction_target.data, instruction_binding)
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, f"Could not bind Instructions: {exc}") from exc

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
            if instruction_binding is not None:
                # Preserve the exact source definition. A later source edit must be reviewed
                # and rebound; execution checks the revision rather than silently drifting.
                version = (
                    await session.exec(
                        select(FlowVersion)
                        .where(
                            FlowVersion.flow_id == instruction_target.id,
                            FlowVersion.user_id == project.user_id,
                        )
                        .order_by(col(FlowVersion.version_number).desc())
                        .limit(1)
                    )
                ).first()
                if version is None or version.data != instruction_target.data:
                    version = await create_flow_version_entry(
                        session,
                        instruction_target.id,
                        project.user_id,
                        data=deepcopy(instruction_target.data),
                        description="Harness Instructions binding",
                    )
                instruction_binding = instruction_binding.model_copy(update={"version_id": str(version.id)})
                config["flow_bindings"] = {"system_prompt": instruction_binding.model_dump()}
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
        if project_type.name == "agent-harness" and "tools" in config:
            try:
                data = compose_tools(
                    data,
                    project_id=str(project.id),
                    agent_id=agent_node_ids(data)[0],
                    targets=[
                        {
                            "id": str(tool.id),
                            "name": tool.name,
                            "data": tool.data,
                            "updated_at": tool.updated_at.isoformat() if tool.updated_at else None,
                        }
                        for tool in tools
                    ],
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
