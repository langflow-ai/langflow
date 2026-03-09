"""Snapshot/flow tool creation, artifact building, and upload for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
import importlib.metadata as md
import io
import json
import re
import zipfile
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from cachetools import func
from ibm_watsonx_orchestrate_core.types.tools.langflow_tool import LangflowTool, create_langflow_tool
from lfx.services.adapters.deployment.exceptions import InvalidContentError, InvalidDeploymentOperationError
from lfx.utils.flow_requirements import generate_requirements_from_flow

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import DEFAULT_LANGFLOW_RUNNER_MODULES
from langflow.services.adapters.deployment.watsonx_orchestrate.utils import (
    dedupe_list,
    normalize_wxo_name,
    require_non_empty_string,
    require_tool_id,
)
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from ibm_watsonx_orchestrate_clients.connections.connections_client import ConnectionsClient
    from ibm_watsonx_orchestrate_clients.tools.tool_client import ToolClient
    from lfx.services.adapters.deployment.schema import BaseFlowArtifact, SnapshotItems

    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


def extract_langflow_artifact_from_zip(artifact_zip_bytes: bytes, *, snapshot_id: str) -> dict[str, Any]:
    """Read and parse the Langflow flow JSON from a WXO snapshot artifact zip."""
    try:
        with zipfile.ZipFile(io.BytesIO(artifact_zip_bytes), "r") as zip_artifact:
            json_members = [name for name in zip_artifact.namelist() if name.lower().endswith(".json")]
            if not json_members:
                msg = f"Snapshot '{snapshot_id}' artifact does not include a flow JSON file."
                raise ValueError(msg)

            # Snapshot upload currently stores exactly one flow JSON payload.
            flow_json_member = json_members[0]
            flow_json_raw = zip_artifact.read(flow_json_member)
    except zipfile.BadZipFile as exc:
        msg = f"Snapshot '{snapshot_id}' artifact is not a valid zip archive."
        raise ValueError(msg) from exc

    try:
        return json.loads(flow_json_raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        msg = f"Snapshot '{snapshot_id}' flow artifact is not valid UTF-8 JSON."
        raise ValueError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"Snapshot '{snapshot_id}' flow artifact contains invalid JSON."
        raise ValueError(msg) from exc


def build_langflow_artifact_bytes(
    *,
    tool: Any,
    flow_definition: dict[str, Any],
    flow_filename: str | None = None,
) -> bytes:
    filename = flow_filename or f"{tool.__tool_spec__.name}.json"
    lfx_requirement = "lfx>=0.3.0rc3"  # TODO: handle dev environments consistently.
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
    tool_client: ToolClient,
    *,
    tool_id: str,
    artifact_bytes: bytes,
) -> dict[str, Any]:
    file_obj = io.BytesIO(artifact_bytes)
    return tool_client._post(  # noqa: SLF001
        f"/tools/{tool_id}/upload",
        files={"file": (f"{tool_id}.zip", file_obj, "application/zip", {"Expires": "0"})},
    )


def resolve_lfx_runner_requirement(tool: LangflowTool) -> str:
    # Prefer whichever runner package is actually installed right now.
    tool_requirements = list(getattr(tool, "requirements", []) or [])
    for requirement in tool_requirements:
        requirement_name = re.split(r"[<>=~!\[\s;]", requirement.strip(), maxsplit=1)[0].lower()
        if requirement_name in DEFAULT_LANGFLOW_RUNNER_MODULES:
            return _pin_requirement_name(requirement_name)

    for runner_package in ("lfx-nightly", "lfx"):
        try:
            return _pin_requirement_name(runner_package)
        except md.PackageNotFoundError:
            continue

    return "lfx"


def resolve_snapshot_connections(
    *,
    connections_client: ConnectionsClient,
    config_id: str | None,
) -> dict[str, str]:
    connections: dict[str, str] = {}
    if config_id is not None:
        app_id = require_non_empty_string(
            config_id,
            field_name="config_id",
            error_message="Snapshot binding requires non-empty 'config_id'.",
        )
        connection = connections_client.get_draft_by_app_id(app_id=app_id)
        if not connection:
            msg = f"Connection '{app_id}' not found."
            raise ValueError(msg)
        connections = {app_id: connection.connection_id}
    return connections


def sync_langflow_tool_connections(
    *,
    clients: WxOClient,
    tool_ids: list[str],
    config_id: str | None,
    connection_id: str | None,
) -> None:
    if not tool_ids:
        return

    tools = clients.tool.get_drafts_by_ids(tool_ids)
    tools_by_id = {str(tool.get("id")): tool for tool in tools if isinstance(tool, dict) and tool.get("id")}

    for tool_id in tool_ids:
        tool = tools_by_id.get(tool_id)
        if not tool:
            msg = f"Snapshot '{tool_id}' not found."
            raise ValueError(msg)

        langflow_binding = tool.get("binding", {}).get("langflow", {})
        if not langflow_binding:
            continue

        current_connections = langflow_binding.get("connections")
        if not isinstance(current_connections, dict):
            current_connections = {}

        updated_connections = dict(current_connections)
        # A null config update means "no new connection to add", not "clear existing".
        if config_id is None:
            continue
        if connection_id is not None:
            updated_connections[config_id] = connection_id

        if updated_connections == current_connections:
            continue

        # TODO: just send the request?
        update_payload: dict[str, Any] = {}
        update_payload.setdefault("binding", {}).setdefault("langflow", {})["connections"] = updated_connections
        clients.tool.update(tool_id, update_payload)


def create_wxo_flow_tool(
    *,
    flow_payload: BaseFlowArtifact,
    connections: dict[str, str],
    app_id: str | None = None,
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
        app_id: Connection app id used to namespace load_from_db variable references.
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

    if app_id is not None:
        flow_definition = prefix_flow_global_variable_references(
            flow_definition,
            app_id=app_id,
        )

    # Fallback for flows that don't include last_tested_version in payload
    if not flow_definition.get("last_tested_version"):
        detected_version = (get_version_info() or {}).get("version")
        if not detected_version:
            msg = "Unable to determine running Langflow version for snapshot creation."
            raise ValueError(msg)
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


async def create_and_upload_wxo_flow_tools(
    *,
    tool_client: ToolClient,
    flow_payloads: list[BaseFlowArtifact],
    connections: dict[str, str],
    app_id: str | None = None,
    tool_name_prefix: str,
) -> list[str]:
    specs = [
        create_wxo_flow_tool(
            flow_payload=flow_payload,
            connections=connections,
            app_id=app_id,
            tool_name_prefix=tool_name_prefix,
        )
        for flow_payload in flow_payloads
    ]
    return await asyncio.gather(
        *(
            upload_wxo_flow_tool(
                tool_client=tool_client,
                tool_payload=tool_payload,
                artifact_bytes=artifact_bytes,
            )
            for tool_payload, artifact_bytes in specs
        )
    )


async def upload_wxo_flow_tool(
    *,
    tool_client: ToolClient,
    tool_payload: dict[str, Any],
    artifact_bytes: bytes,
) -> str:
    tool_response = await asyncio.to_thread(tool_client.create, tool_payload)
    tool_id = require_tool_id(tool_response)

    await asyncio.to_thread(
        upload_tool_artifact_bytes,
        tool_client,
        tool_id=tool_id,
        artifact_bytes=artifact_bytes,
    )
    return tool_id


def prefix_flow_global_variable_references(
    flow_definition: dict[str, Any],
    *,
    app_id: str,
) -> dict[str, Any]:
    """Prefix load-from-db global variable names with the WXO app id."""
    normalized_app_id = app_id.strip()
    if not normalized_app_id:
        return flow_definition

    prefix = f"{normalized_app_id}_"

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("load_from_db") is True and isinstance(value.get("value"), str):
                variable_name = value["value"].strip()
                if variable_name and not variable_name.startswith(prefix):
                    # TODO: sometimes the user wants to keep a raw value
                    # figure out what the exact conditions for this are
                    value["value"] = f"{prefix}{variable_name}"
            for child in value.values():
                _walk(child)
            return

        if isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(flow_definition)
    return flow_definition


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
    user_id: Any,
    app_id: str,
    flows: list[BaseFlowArtifact],
    db: Any,
    tool_name_prefix: str,
    *,
    client_cache: dict[str, Any],
) -> list[str]:
    """Create langflow tools in wxo and connect them to the given app_id."""
    from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_provider_clients
    from langflow.services.adapters.deployment.watsonx_orchestrate.core.config import validate_connection

    if not tool_name_prefix.strip():
        msg = "Snapshot creation requires a non-empty tool_name_prefix."
        raise InvalidDeploymentOperationError(message=msg)

    clients = await get_provider_clients(
        user_id=user_id,
        db=db,
        client_cache=client_cache,
    )

    connection = validate_connection(clients.connections, app_id=app_id)

    return await create_and_upload_wxo_flow_tools(
        tool_client=clients.tool,
        flow_payloads=flows,
        connections={app_id: connection.connection_id},
        app_id=app_id,
        tool_name_prefix=tool_name_prefix,
    )


async def create_langflow_flow_tool(
    *,
    user_id: Any,
    config_id: str | None = None,
    flow_payload: BaseFlowArtifact,
    db: Any,
    client_cache: dict[str, Any],
) -> str:
    from langflow.services.adapters.deployment.watsonx_orchestrate.client import get_provider_clients

    clients = await get_provider_clients(
        user_id=user_id,
        db=db,
        client_cache=client_cache,
    )
    connections = resolve_snapshot_connections(
        connections_client=clients.connections,
        config_id=config_id,
    )
    tool_payload, artifact_bytes = create_wxo_flow_tool(
        flow_payload=flow_payload,
        connections=connections,
        app_id=config_id,
        tool_name_prefix=f"lf_{uuid4().hex[:6]}_",
    )

    return await upload_wxo_flow_tool(
        tool_client=clients.tool,
        tool_payload=tool_payload,
        artifact_bytes=artifact_bytes,
    )


@func.ttl_cache(maxsize=1, ttl=2)
def _pin_requirement_name(package_name: str) -> str:
    version = md.version(package_name)
    return f"{package_name}=={version}"
