"""Snapshot/flow tool creation, artifact building, and upload for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
import copy
import importlib.metadata as md
import io
import json
import os
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cachetools import func
from fastapi import HTTPException
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import create_langflow_tool
from lfx.log.logger import logger
from lfx.services.adapters.deployment.exceptions import (
    InvalidContentError,
    InvalidDeploymentOperationError,
)
from lfx.utils.flow_requirements import generate_requirements_from_flow

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import ErrorPrefix
from langflow.services.adapters.deployment.watsonx_orchestrate.core.retry import retry_create
from langflow.services.adapters.deployment.watsonx_orchestrate.payloads import (
    WatsonxFlowArtifactProviderData,
    WatsonxToolRefBinding,
)
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    dedupe_list,
    normalize_wxo_name,
    raise_as_deployment_error,
    require_tool_id,
)
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import LangflowTool
    from lfx.services.adapters.deployment.schema import BaseFlowArtifact, SnapshotItems, SnapshotListResult

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


def verify_langflow_owned(tool: dict[str, Any], *, tool_id: str) -> None:
    """Raise ``InvalidContentError`` if the tool lacks ``binding.langflow``.

    Call before any mutating operation on an existing tool to ensure
    Langflow created it.  Tools created manually in the wxO console or
    by other integrations will not have this marker.
    """
    binding = tool.get("binding")
    if not isinstance(binding, dict) or "langflow" not in binding:
        msg = f"Cannot modify tool '{tool_id}': it does not have a Langflow binding and may not be managed by Langflow."
        raise InvalidContentError(message=msg)


def extract_langflow_connections_binding(tool_payload: dict[str, Any]) -> dict[str, str]:
    """Extract ``binding.langflow.connections`` from a provider tool payload.

    Read-path helper: returns ``{}`` for missing or malformed nested shapes
    without mutating the input payload.
    """
    binding = tool_payload.get("binding")
    if not isinstance(binding, dict):
        return {}
    langflow = binding.get("langflow")
    if not isinstance(langflow, dict):
        return {}
    connections = langflow.get("connections")
    return connections if isinstance(connections, dict) else {}


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
        tool = tool_by_id[tool_id]
        verify_langflow_owned(tool, tool_id=tool_id)

        original_tool = to_writable_tool_payload(tool)
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
    logger.debug("build_langflow_artifact_bytes: filename='%s', requirements=%s", filename, requirements)

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
    flow_payload: BaseFlowArtifact[WatsonxFlowArtifactProviderData],
    connections: dict[str, str],
) -> tuple[dict[str, Any], bytes]:
    """Create a Watsonx Orchestrate flow tool specification.

    Given a flow payload and connections dictionary,
    create a Watsonx Orchestrate flow tool specification
    and the supporting artifacts of the requirements.txt
    and the flow json file.

    Args:
        flow_payload: The flow payload to create the tool specification for.
        connections: The connections dictionary to create the tool specification for.

    Returns:
        Tuple[dict[str, Any], bytes]: a tuple containing:
            - tool_payload: The Watsonx Orchestrate flow tool specification.
            - artifacts: The supporting artifacts (the requirements.txt
                and the flow json file) for the tool.
    """
    # provider_data might break tool runtime expectations with unexpected top-level keys
    flow_definition = flow_payload.model_dump(exclude={"provider_data"})
    logger.debug(
        "create_wxo_flow_tool: flow name='%s', id='%s', connections=%s",
        flow_definition.get("name"),
        flow_definition.get("id"),
        connections,
    )

    flow_provider_data = flow_payload.provider_data
    if not isinstance(flow_provider_data, WatsonxFlowArtifactProviderData):
        msg = "Flow payload provider_data must be a WatsonxFlowArtifactProviderData model instance."
        raise InvalidContentError(message=msg)
    project_id = str(flow_provider_data.project_id).strip()

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
        tool_payload["name"] = normalize_wxo_name(current_name)

    (tool_payload.setdefault("binding", {}).setdefault("langflow", {})["project_id"]) = project_id
    logger.debug(
        "create_wxo_flow_tool: tool name='%s', project_id='%s', binding=%s",
        tool_payload.get("name"),
        project_id,
        tool_payload.get("binding", {}).get("langflow"),
    )

    artifacts: bytes = build_langflow_artifact_bytes(
        tool=tool,
        flow_definition=flow_definition,
    )

    return tool_payload, artifacts


async def create_and_upload_wxo_flow_tools(
    *,
    clients: WxOClient,
    flow_payloads: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]],
    connections: dict[str, str],
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
    )


async def create_and_upload_wxo_flow_tools_with_bindings(
    *,
    clients: WxOClient,
    tool_bindings: list[FlowToolBindingSpec],
) -> list[str]:
    logger.debug("create_and_upload_wxo_flow_tools_with_bindings: %d tool bindings", len(tool_bindings))
    specs = [
        create_wxo_flow_tool(
            flow_payload=tool_binding.flow_payload,
            connections=tool_binding.connections,
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
    tool_name = tool_payload.get("name")
    try:
        tool_response = await retry_create(asyncio.to_thread, clients.tool.create, tool_payload)
    except (ClientAPIException, HTTPException) as exc:
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.CREATE,
            log_msg="Unexpected provider error during wxO tool create",
            resource="tool",
            resource_name=tool_name,
        )
    tool_id = require_tool_id(tool_response)
    logger.debug(
        "upload_wxo_flow_tool: created tool_id='%s', uploading artifact (%d bytes)", tool_id, len(artifact_bytes)
    )
    if created_tool_ids_journal is not None:
        created_tool_ids_journal.append(tool_id)

    try:
        await retry_create(
            asyncio.to_thread,
            upload_tool_artifact_bytes,
            clients,
            tool_id=tool_id,
            artifact_bytes=artifact_bytes,
        )
    except (ClientAPIException, HTTPException) as exc:
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.CREATE,
            log_msg="Unexpected provider error during wxO tool artifact upload",
            resource="tool",
            resource_name=tool_name,
        )
    return tool_id


def build_snapshot_tool_names(
    *,
    snapshots: SnapshotItems | None,
) -> list[str]:
    if snapshots is None:
        return []

    tool_names: list[str] = []
    for snapshot in snapshots.raw_payloads:
        normalized_tool_name = normalize_wxo_name(str(snapshot.name))
        if not normalized_tool_name:
            msg = "Snapshot name must include at least one alphanumeric character."
            raise InvalidContentError(message=msg)
        tool_names.append(normalized_tool_name)
    return tool_names


async def process_raw_flows_with_app_id(
    clients: WxOClient,
    app_id: str,
    flows: list[BaseFlowArtifact[WatsonxFlowArtifactProviderData]],
) -> list[WatsonxToolRefBinding]:
    """Create langflow tools in wxO and connect them to the given app_id."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection

    connection = await validate_connection(clients.connections, app_id=app_id)

    created_tool_ids = await create_and_upload_wxo_flow_tools(
        clients=clients,
        flow_payloads=flows,
        connections={app_id: connection.connection_id},
    )
    if len(created_tool_ids) != len(flows):
        msg = "Flow upload result mismatch: created tool ids count does not match the number of flow payloads."
        raise InvalidDeploymentOperationError(message=msg)
    return [
        WatsonxToolRefBinding(
            source_ref=_resolve_flow_source_ref(flow_payload),
            tool_id=tool_id,
        )
        for flow_payload, tool_id in zip(flows, created_tool_ids, strict=True)
    ]


def _resolve_flow_source_ref(flow_payload: BaseFlowArtifact[WatsonxFlowArtifactProviderData]) -> str:
    provider_data = flow_payload.provider_data
    if not isinstance(provider_data, WatsonxFlowArtifactProviderData):
        msg = "Flow payload provider_data must be a WatsonxFlowArtifactProviderData model instance."
        raise InvalidContentError(message=msg)
    source_ref = str(provider_data.source_ref).strip()
    if source_ref:
        return source_ref
    msg = "Flow payload must include provider_data.source_ref for snapshot correlation."
    raise InvalidContentError(message=msg)


@func.ttl_cache(maxsize=1, ttl=60)
def _pin_requirement_name(package_name: str) -> str:
    return f"{package_name}=={md.version(package_name)}"


def _resolve_lfx_requirement() -> str:
    """Pin lfx to the installed version, falling back to a minimum spec.

    If the ``WXO_LFX_REQUIREMENT_OVERRIDE`` environment variable is set, its
    value is used verbatim as the lfx requirement line (e.g.
    ``lfx-nightly==0.4.0.dev32``) instead of resolving from the installed
    package metadata.
    """
    override = os.environ.get("WXO_LFX_REQUIREMENT_OVERRIDE", "").strip()
    if override:
        logger.debug("Using wxO lfx requirement override: %s", override)
        return override
    try:
        return _pin_requirement_name("lfx")
    except (md.PackageNotFoundError, ValueError) as exc:
        # Prefer failing fast here instead of falling back, as wxO does not
        # return useful error messages on dependency failures during deployment.
        message = "Could not determine installed lfx version. Failing deployment."
        raise ValueError(message) from exc


async def verify_tools_by_ids(
    clients: WxOClient,
    snapshot_ids: list[str],
) -> SnapshotListResult:
    """Fetch tools by ID and return only those that still exist on the provider."""
    from lfx.services.adapters.deployment.schema import SnapshotItem, SnapshotListResult

    if not snapshot_ids:
        return SnapshotListResult(snapshots=[])

    unique_ids = list(dict.fromkeys(snapshot_ids))
    try:
        tools = await asyncio.to_thread(clients.tool.get_drafts_by_ids, unique_ids)
    except Exception as exc:  # noqa: BLE001
        raise_as_deployment_error(
            exc,
            error_prefix=ErrorPrefix.LIST,
            log_msg="Unexpected error while verifying wxO tool snapshots by ID",
        )

    snapshots: list[SnapshotItem] = []
    for tool in tools or []:
        if not isinstance(tool, dict) or not tool.get("id"):
            continue
        connections = extract_langflow_connections_binding(tool)
        normalized_connections: dict[str, str] = {
            key: value
            for raw_key, raw_value in connections.items()
            if isinstance(raw_key, str)
            and isinstance(raw_value, str)
            and (key := raw_key.strip())
            and (value := raw_value.strip())
        }

        if len(normalized_connections) < len(connections):
            logger.warning(
                "Tool %s returned malformed langflow connection bindings; defaulting to empty mapping",
                tool["id"],
            )
            provider_data: dict[str, dict[str, str]] = {"connections": {}}
        else:
            provider_data = {"connections": normalized_connections}
        snapshots.append(
            SnapshotItem(
                id=tool["id"],
                name=tool.get("name") or tool["id"],
                provider_data=provider_data,
            )
        )
    return SnapshotListResult(snapshots=snapshots)
