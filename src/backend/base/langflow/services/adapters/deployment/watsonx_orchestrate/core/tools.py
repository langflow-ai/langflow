"""Snapshot/flow tool creation, artifact building, and upload for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
import copy
import importlib.metadata as md
import io
import json
import logging
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cachetools import func
from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import LangflowTool
from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import create_langflow_tool as _create_langflow_tool
from lfx.services.adapters.deployment.exceptions import InvalidContentError, InvalidDeploymentOperationError
from lfx.utils.flow_requirements import generate_requirements_from_flow

from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import retry_create
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    dedupe_list,
    normalize_wxo_name,
    require_tool_id,
)
from langflow.utils.version import get_version_info

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from lfx.services.adapters.deployment.schema import BaseFlowArtifact, SnapshotItems

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient

# TODO: ensure all fields from here are used
#  https://developer.watson-orchestrate.ibm.com/apis/tools/patch-a-tool
#  as it is a PUT endpoint (don't want to lose any fields)
_WRITABLE_TOOL_FIELDS = (
    "description",
    "permission",
    "name",
    "display_name",
    "input_schema",
    "output_schema",
    "binding",
    "tags",
    "is_async",
    "restrictions",
    "bundled_agent_id",
)


@dataclass(slots=True)
class FlowToolBindingSpec:
    flow_payload: BaseFlowArtifact
    connections: dict[str, str]


class ToolUploadBatchError(RuntimeError):
    """Raised when a concurrent tool-upload batch partially succeeds."""

    def __init__(self, *, created_tool_ids: list[str], errors: list[Exception]) -> None:
        self.created_tool_ids = created_tool_ids
        self.errors = errors
        super().__init__("One or more tool uploads failed.")


def to_writable_tool_payload(tool: dict[str, Any]) -> dict[str, Any]:
    """Build tool payload accepted by wxO tool update endpoint."""
    return {field: copy.deepcopy(tool[field]) for field in _WRITABLE_TOOL_FIELDS if field in tool}


def _ensure_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    """Return ``parent[key]`` as a dict, replacing non-dict values with ``{}``."""
    value = parent.setdefault(key, {})
    if not isinstance(value, dict):
        logger.warning(
            "Expected dict at key '%s' but found %s; replacing with empty dict",
            key,
            type(value).__name__,
        )
        value = {}
        parent[key] = value
    return value


def ensure_langflow_connections_binding(tool_payload: dict[str, Any]) -> dict[str, str]:
    """Ensure ``binding.langflow.connections`` exists in *tool_payload* and return the mutable dict.

    Non-dict values at any nesting level are silently replaced with ``{}``.
    We intentionally do *not* raise on a malformed shape because
    callers of this function are *writing* connection bindings into
    these payloads (and the pre-mutation snapshot is captured for rollback),
    replacing an unexpected value is traded with explcitiness
    to prevent a stubbornly failing update.
    """
    binding = _ensure_dict(tool_payload, "binding")
    langflow = _ensure_dict(binding, "langflow")
    return _ensure_dict(langflow, "connections")


async def update_existing_tool_connection_bindings(
    *,
    clients: WxOClient,
    existing_target_tool_ids: list[str],
    resolved_connections: dict[str, str],
    original_tools: dict[str, dict[str, Any]],
) -> None:
    """Apply resolved connection bindings to existing tools.

    Captures original writable payloads for rollback before any update call.
    Raises ``InvalidContentError`` when any expected tool id is missing.
    """
    if not existing_target_tool_ids:
        return

    tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, existing_target_tool_ids)
    tool_by_id = {str(tool.get("id")): tool for tool in tools if isinstance(tool, dict) and tool.get("id")}
    missing_tool_ids = [tool_id for tool_id in existing_target_tool_ids if tool_id not in tool_by_id]
    if missing_tool_ids:
        missing_ids = ", ".join(missing_tool_ids)
        msg = f"Snapshot tool(s) not found: {missing_ids}"
        raise InvalidContentError(message=msg)

    tool_updates: list[tuple[str, dict[str, Any]]] = []
    for tool_id in existing_target_tool_ids:
        original_tool = to_writable_tool_payload(tool_by_id[tool_id])
        original_tools[tool_id] = original_tool
        writable_tool = copy.deepcopy(original_tool)
        connections = ensure_langflow_connections_binding(writable_tool)
        connections.update(resolved_connections)
        tool_updates.append((tool_id, writable_tool))

    await asyncio.gather(
        *(
            retry_create(asyncio.to_thread, clients.tool.update, tool_id, writable_tool)
            for tool_id, writable_tool in tool_updates
        )
    )


def extract_langflow_artifact_from_zip(artifact_zip_bytes: bytes, *, snapshot_id: str) -> dict[str, Any]:
    """Read and parse the Langflow flow JSON from a wxO snapshot artifact zip."""
    try:
        with zipfile.ZipFile(io.BytesIO(artifact_zip_bytes), "r") as zip_artifact:
            json_members = [name for name in zip_artifact.namelist() if name.lower().endswith(".json")]
            if not json_members:
                msg = f"Snapshot '{snapshot_id}' artifact does not include a flow JSON file."
                raise InvalidContentError(message=msg)

            flow_json_member = json_members[0]
            flow_json_raw = zip_artifact.read(flow_json_member)
    except InvalidContentError:
        raise
    except zipfile.BadZipFile as exc:
        msg = f"Snapshot '{snapshot_id}' artifact is not a valid zip archive."
        raise InvalidContentError(message=msg) from exc

    try:
        return json.loads(flow_json_raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        msg = f"Snapshot '{snapshot_id}' flow artifact is not valid UTF-8 JSON."
        raise InvalidContentError(message=msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Snapshot '{snapshot_id}' flow artifact contains invalid JSON."
        raise InvalidContentError(message=msg) from exc


def build_langflow_artifact_bytes(
    *,
    tool: LangflowTool,
    flow_definition: dict[str, Any],
    flow_filename: str | None = None,
) -> bytes:
    filename = flow_filename or f"{tool.__tool_spec__.name}.json"
    lfx_requirement = _resolve_lfx_requirement()
    requirements = generate_requirements_from_flow(
        flow_definition,
        include_lfx=False,
        pin_versions=True,
    )
    requirements = [lfx_requirement, *requirements]
    requirements = dedupe_list(requirements)
    requirements_content = "\n".join(requirements) + "\n"
    flow_content = json.dumps(flow_definition, indent=2)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_tool_artifacts:
        zip_tool_artifacts.writestr(filename, flow_content)
        zip_tool_artifacts.writestr("requirements.txt", requirements_content)
        zip_tool_artifacts.writestr("bundle-format", "2.0.0\n")
    return buffer.getvalue()


def upload_tool_artifact_bytes(
    clients: WxOClient,
    *,
    tool_id: str,
    artifact_bytes: bytes,
) -> dict[str, Any]:
    file_obj = io.BytesIO(artifact_bytes)
    return clients.upload_tool_artifact(
        tool_id,
        files={"file": (f"{tool_id}.zip", file_obj, "application/zip", {"Expires": "0"})},
    )


def create_wxo_flow_tool(
    *,
    flow_payload: BaseFlowArtifact,
    connections: dict[str, str],
    tool_name_prefix: str,
) -> tuple[dict[str, Any], bytes]:
    """Create a Watsonx Orchestrate flow tool specification.

    Given a flow payload and connections dictionary,
    create a Watsonx Orchestrate flow tool specification
    and the supporting artifacts of the requirements.txt
    and the flow json file.

    Args:
        flow_payload: The flow payload to create the tool specification for.
        connections: The connections dictionary to create the tool specification for.
        tool_name_prefix: Deterministic prefix for the resulting tool name.

    Returns:
        Tuple[dict[str, Any], bytes]: a tuple containing:
            - tool_payload: The Watsonx Orchestrate flow tool specification.
            - artifacts: The supporting artifacts (the requirements.txt
                and the flow json file) for the tool.
    """
    flow_definition = flow_payload.model_dump()

    flow_provider_data = flow_definition.pop("provider_data", None)

    if not isinstance(flow_provider_data, dict):
        msg = "Flow payload must include provider_data with a non-empty project_id for Watsonx deployment."
        raise InvalidContentError(message=msg)
    project_id = str(flow_provider_data.get("project_id") or "").strip()
    if not project_id:
        msg = "Flow payload must include provider_data with a non-empty project_id for Watsonx deployment."
        raise InvalidContentError(message=msg)

    flow_definition.update(
        {
            "name": normalize_wxo_name(flow_definition.get("name") or ""),
            "id": str(flow_definition.get("id")),
        }
    )

    # Fallback for flows that don't include last_tested_version in payload
    if not flow_definition.get("last_tested_version"):
        detected_version = (get_version_info() or {}).get("version")
        if not detected_version:
            msg = "Unable to determine running Langflow version for snapshot creation."
            raise InvalidContentError(message=msg)
        flow_definition["last_tested_version"] = detected_version

    tool: LangflowTool = create_langflow_tool(
        tool_definition=flow_definition,
        connections=connections,
        show_details=False,
    )

    tool_payload = tool.__tool_spec__.model_dump(
        mode="json",
        exclude_unset=True,
        exclude_none=True,
        by_alias=True,
    )

    current_name = str(tool_payload.get("name") or "").strip()

    if current_name:
        normalized_current_name = normalize_wxo_name(current_name)
        tool_payload["name"] = f"{tool_name_prefix}{normalized_current_name}"

    (tool_payload.setdefault("binding", {}).setdefault("langflow", {})["project_id"]) = project_id

    artifacts: bytes = build_langflow_artifact_bytes(
        tool=tool,
        flow_definition=flow_definition,
    )

    return tool_payload, artifacts


def create_langflow_tool(
    *,
    tool_definition: dict[str, Any],
    connections: dict[str, str],
    show_details: bool,
) -> LangflowTool:
    """Module-level wrapper to keep tool creation monkeypatchable in tests."""
    return _create_langflow_tool(
        tool_definition=tool_definition,
        connections=connections,
        show_details=show_details,
    )


async def create_and_upload_wxo_flow_tools(
    *,
    clients: WxOClient,
    flow_payloads: list[BaseFlowArtifact],
    connections: dict[str, str],
    tool_name_prefix: str,
) -> list[str]:
    tool_bindings = [
        FlowToolBindingSpec(
            flow_payload=flow_payload,
            connections=connections,
        )
        for flow_payload in flow_payloads
    ]
    return await create_and_upload_wxo_flow_tools_with_bindings(
        clients=clients,
        tool_bindings=tool_bindings,
        tool_name_prefix=tool_name_prefix,
    )


async def create_and_upload_wxo_flow_tools_with_bindings(
    *,
    clients: WxOClient,
    tool_bindings: list[FlowToolBindingSpec],
    tool_name_prefix: str,
) -> list[str]:
    specs = [
        create_wxo_flow_tool(
            flow_payload=tool_binding.flow_payload,
            connections=tool_binding.connections,
            tool_name_prefix=tool_name_prefix,
        )
        for tool_binding in tool_bindings
    ]
    created_tool_ids_journal: list[str] = []
    results = await asyncio.gather(
        *(
            upload_wxo_flow_tool(
                clients=clients,
                tool_payload=tool_payload,
                artifact_bytes=artifact_bytes,
                created_tool_ids_journal=created_tool_ids_journal,
            )
            for tool_payload, artifact_bytes in specs
        ),
        return_exceptions=True,
    )
    errors: list[Exception] = []
    created_tool_ids: list[str] = []
    for result in results:
        if isinstance(result, BaseException):
            if isinstance(result, Exception):
                errors.append(result)
            else:
                errors.append(RuntimeError(f"Tool upload failed with non-standard exception: {type(result).__name__}"))
            continue
        created_tool_ids.append(result)
    if errors:
        raise ToolUploadBatchError(created_tool_ids=dedupe_list(created_tool_ids_journal), errors=errors)
    return created_tool_ids


async def upload_wxo_flow_tool(
    *,
    clients: WxOClient,
    tool_payload: dict[str, Any],
    artifact_bytes: bytes,
    created_tool_ids_journal: list[str] | None = None,
) -> str:
    tool_response = await retry_create(asyncio.to_thread, clients.tool.create, tool_payload)
    tool_id = require_tool_id(tool_response)
    if created_tool_ids_journal is not None:
        created_tool_ids_journal.append(tool_id)

    await retry_create(
        asyncio.to_thread,
        upload_tool_artifact_bytes,
        clients,
        tool_id=tool_id,
        artifact_bytes=artifact_bytes,
    )
    return tool_id


def build_snapshot_tool_names(
    *,
    snapshots: SnapshotItems | None,
    tool_name_prefix: str,
) -> list[str]:
    if snapshots is None:
        return []

    tool_names: list[str] = []
    for snapshot in snapshots.raw_payloads:
        normalized_tool_name = normalize_wxo_name(str(snapshot.name))
        if not normalized_tool_name:
            msg = "Snapshot name must include at least one alphanumeric character."
            raise InvalidContentError(message=msg)
        tool_names.append(f"{tool_name_prefix}{normalized_tool_name}")
    return tool_names


async def process_raw_flows_with_app_id(
    clients: WxOClient,
    app_id: str,
    flows: list[BaseFlowArtifact],
    tool_name_prefix: str,
) -> list[str]:
    """Create langflow tools in wxO and connect them to the given app_id."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection

    if not tool_name_prefix.strip():
        msg = "Snapshot creation requires a non-empty tool_name_prefix."
        raise InvalidDeploymentOperationError(message=msg)

    connection = await validate_connection(clients.connections, app_id=app_id)

    return await create_and_upload_wxo_flow_tools(
        clients=clients,
        flow_payloads=flows,
        connections={app_id: connection.connection_id},
        tool_name_prefix=tool_name_prefix,
    )


# TODO(WXO): find a way to make this fallback not hard-coded.
_LFX_MINIMUM_REQUIREMENT = "lfx>=0.3.0"


@func.ttl_cache(maxsize=1, ttl=60)
def _pin_requirement_name(package_name: str) -> str:
    return f"{package_name}=={md.version(package_name)}"


def _resolve_lfx_requirement() -> str:
    """Pin lfx to the installed version, falling back to a minimum spec."""
    try:
        return _pin_requirement_name("lfx")
    except (md.PackageNotFoundError, ValueError):
        logger.warning(
            "Could not determine installed lfx version; falling back to minimum requirement '%s'",
            _LFX_MINIMUM_REQUIREMENT,
        )
        return _LFX_MINIMUM_REQUIREMENT
