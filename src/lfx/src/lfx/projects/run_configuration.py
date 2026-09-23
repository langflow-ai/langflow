"""Immutable Agent configuration records with redacted model parameters."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretBytes, SecretStr, model_serializer, model_validator

from lfx.base.agents.harness import HarnessRuntimeConfig
from lfx.projects.bindings import BINDING_ORIGIN, flow_revision
from lfx.projects.flow_slots import ProjectFlowBindings
from lfx.projects.local_tools import LocalToolBinding
from lfx.projects.skills import HarnessSkills, parse_harness_skills
from lfx.projects.tool_packs import ToolPackToolBinding
from lfx.utils.url_redaction import redact_urls_in_text

CONFIGURATIONS_STATE_KEY = "harness_run_configurations"
_SENSITIVE = re.compile(
    r"api.?key|password|secret|credential|authorization|access.?token|refresh.?token|private.?key", re.IGNORECASE
)
_MAX_DEPTH = 20


def public_parameters(value: object, *, _depth: int = 0) -> object:
    """Copy JSON values without serializing SDK clients, secrets, or object reprs."""
    if isinstance(value, (SecretStr, SecretBytes)) or _depth > _MAX_DEPTH:
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(key): "[redacted]"
            if _SENSITIVE.search(str(key)) or str(key).lower() in {"token", "auth"}
            else public_parameters(item, _depth=_depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [public_parameters(item, _depth=_depth + 1) for item in value]
    if isinstance(value, str):
        try:
            return redact_urls_in_text(value)
        except ValueError:
            return "[redacted URL]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return f"[unavailable: {type(value).__name__}]"


class ModelConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    implementation: str
    name: str
    parameters: dict = Field(default_factory=dict)


class ToolConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    input_schema: dict
    return_direct: bool = False
    approval_actions: tuple[str, ...] = ()
    tool_pack: ToolPackToolBinding | None = None
    local_flow: LocalToolBinding | None = None

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        value = handler(self)
        # Older report configuration hashes must remain valid.
        if self.local_flow is None:
            value.pop("local_flow", None)
        return value


class AgentConfiguration(BaseModel):
    """A configuration used by an Agent attempt, retained through checkpoint resumes.

    The resolved prompt and runtime values come from the instantiated component.
    The flow hash identifies its graph definition, whose runtime overrides are
    recorded separately. Model parameters use the provider's identifying parameters;
    credentials, clients, and transport state are deliberately not serialized.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    revision: str = ""
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    flow_id: str | None = None
    agent_node_id: str
    flow_revision: str | None = None
    component_revision: str | None = None
    model: ModelConfiguration
    system_prompt: str
    runtime: HarnessRuntimeConfig
    history_messages: int
    loaded_history_messages: int
    tool_retry_count: int
    tools: tuple[ToolConfiguration, ...] = ()
    flow_bindings: ProjectFlowBindings = Field(default_factory=ProjectFlowBindings)
    skills: HarnessSkills | None = None

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        value = handler(self)
        if self.skills is None:
            value.pop("skills", None)
        return value

    @model_validator(mode="after")
    def identify_configuration(self) -> AgentConfiguration:
        definition = self.model_dump(mode="json", exclude={"revision", "captured_at"})
        revision = hashlib.sha256(json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if self.revision and self.revision != revision:
            msg = "Configuration revision does not match its recorded values."
            raise ValueError(msg)
        object.__setattr__(self, "revision", revision)
        return self


def capture_agent_configuration(component, model, policy: HarnessRuntimeConfig) -> AgentConfiguration:
    """Record resolved values without querying current project configuration later."""
    graph = component.graph
    data = getattr(graph, "raw_graph_data", None) or {}
    vertex = getattr(component, "_vertex", None)
    node_data = getattr(vertex, "data", {}) or {}
    code = node_data.get("node", {}).get("template", {}).get("code", {}).get("value")
    bindings = {}
    for field, input_name, empty in (
        ("hooks", "hook_bindings", []),
        ("context_strategy", "context_binding", None),
        ("compaction", "compaction_binding", None),
        ("tool_policy", "permission_binding", None),
    ):
        raw = getattr(component, input_name, "") or ""
        value = json.loads(raw) if raw.strip() else empty
        bindings[field] = None if value == {} else value
    # The generated Instructions adapter carries the reviewed source reference.
    # Record it only when it actually feeds this Agent's system_prompt input.
    incoming = {
        edge.get("source")
        for edge in data.get("edges", [])
        if edge.get("target") == component._id  # noqa: SLF001
        and edge.get("data", {}).get("targetHandle", {}).get("fieldName") == "system_prompt"
    }
    for node in data.get("nodes", []):
        origin = node.get("data", {}).get(BINDING_ORIGIN)
        if node.get("id") in incoming and origin:
            bindings["system_prompt"] = {
                key: value for key, value in origin.items() if key not in {"project_id", "field_name"}
            }
    tools = []
    for tool in component.tools or []:
        schema = tool.tool_call_schema
        schema = schema if isinstance(schema, dict) else schema.model_json_schema()
        metadata = tool.metadata or {}
        tools.append(
            ToolConfiguration(
                name=tool.name,
                description=tool.description,
                input_schema=public_parameters(schema),
                return_direct=tool.return_direct,
                approval_actions=tuple(metadata.get("approval_actions") or ()),
                tool_pack=ToolPackToolBinding.model_validate(metadata["harness_tool_pack"])
                if metadata.get("harness_tool_pack")
                else None,
                local_flow=LocalToolBinding.model_validate(metadata["harness_local_tool"])
                if metadata.get("harness_local_tool")
                else None,
            )
        )
    name = getattr(model, "model_name", None) or getattr(model, "model", None) or getattr(model, "_llm_type", "")
    parameters = getattr(model, "_identifying_params", {})
    skills = (
        parse_harness_skills(component.skill_bindings) if getattr(component, "skill_bindings", "").strip() else None
    )
    return AgentConfiguration(
        skills=skills,
        flow_id=str(graph.flow_id) if getattr(graph, "flow_id", None) else None,
        agent_node_id=component._id,  # noqa: SLF001
        flow_revision=flow_revision(data) if data.get("nodes") else None,
        component_revision=hashlib.sha256(code.encode()).hexdigest() if isinstance(code, str) else None,
        model=ModelConfiguration(
            implementation=f"{type(model).__module__}.{type(model).__qualname__}",
            name=name if isinstance(name, str) else type(model).__name__,
            parameters=public_parameters(parameters) if isinstance(parameters, dict) else {},
        ),
        system_prompt=component.system_prompt or "",
        runtime=policy.model_copy(deep=True),
        history_messages=int(getattr(component, "n_messages", 100)),
        loaded_history_messages=len(getattr(component, "chat_history", None) or []),
        tool_retry_count=2
        if (component.tools or (skills and skills.packs)) and getattr(component, "handle_parsing_errors", False)
        else 0,
        tools=tuple(tools),
        flow_bindings=ProjectFlowBindings.model_validate(bindings),
    )
