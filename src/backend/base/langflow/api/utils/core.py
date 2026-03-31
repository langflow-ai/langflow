from __future__ import annotations

import json as _json
from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, HTTPException, Path, Query
from fastapi_pagination import Params
from lfx.log.logger import logger
from lfx.services.deps import injectable_session_scope, injectable_session_scope_readonly
from lfx.utils.validate_cloud import raise_error_if_astra_cloud_disable_component
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.auth.utils import get_current_active_user, get_current_active_user_mcp
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.store.utils import get_lf_version_from_pypi
from langflow.utils.constants import LANGFLOW_GLOBAL_VAR_HEADER_PREFIX

if TYPE_CHECKING:
    from langflow.services.store.schema import StoreComponentCreate


API_WORDS = ["api", "key", "token"]

MAX_PAGE_SIZE = 50
MIN_PAGE_SIZE = 1

CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
CurrentActiveMCPUser = Annotated[User, Depends(get_current_active_user_mcp)]
# DbSession with auto-commit for write operations
DbSession = Annotated[AsyncSession, Depends(injectable_session_scope)]
# DbSessionReadOnly for read-only operations (no auto-commit, reduces lock contention)
DbSessionReadOnly = Annotated[AsyncSession, Depends(injectable_session_scope_readonly)]


def _get_validated_path_segment(value: str, *, label: str = "name") -> str:
    """Validate a path segment to prevent path traversal attacks."""
    if ".." in value or "/" in value or "\\" in value:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label}. Use a simple {label} without directory paths or '..'.",
        )
    return value


def _get_validated_file_name(file_name: str = Path()) -> str:
    return _get_validated_path_segment(file_name, label="file name")


def _get_validated_folder_name(folder_name: str = Path()) -> str:
    return _get_validated_path_segment(folder_name, label="folder name")


ValidatedFileName = Annotated[str, Depends(_get_validated_file_name)]
ValidatedFolderName = Annotated[str, Depends(_get_validated_folder_name)]

# Message to raise if we're in an Astra cloud environment and a component or endpoint is not supported
disable_endpoint_in_astra_cloud_msg = "This endpoint is not supported in Astra cloud environment."


class EventDeliveryType(str, Enum):
    STREAMING = "streaming"
    DIRECT = "direct"
    POLLING = "polling"


def has_api_terms(word: str):
    return "api" in word and ("key" in word or ("token" in word and "tokens" not in word))


def _get_provider_from_template(template: dict) -> str | None:
    """Return provider name from template's model field, if any."""
    model_field = template.get("model")
    if not isinstance(model_field, dict):
        return None
    raw = model_field.get("value")
    if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict):
        return raw[0].get("provider")
    return None


def remove_api_keys(flow: dict):
    """Remove api keys from flow data."""
    for node in flow.get("data", {}).get("nodes", []):
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            continue
        node_inner = node_data.get("node")
        if not isinstance(node_inner, dict):
            continue
        template = node_inner.get("template")
        if not isinstance(template, dict):
            continue
        for value in template.values():
            if isinstance(value, dict) and "name" in value and has_api_terms(value["name"]) and value.get("password"):
                value["value"] = None

    return flow


# ---------------------------------------------------------------------------
# Export normalisation
# ---------------------------------------------------------------------------

# Top-level fields that vary between instances / users without changing logic.
_VOLATILE_TOP_LEVEL: frozenset[str] = frozenset(
    {"updated_at", "created_at", "user_id", "folder_id", "access_type", "gradient"}
)

# Node-level fields that track UI interaction state (position, drag, selection).
_VOLATILE_NODE_FIELDS: frozenset[str] = frozenset({"positionAbsolute", "dragging", "selected"})


def _split_code_to_lines(flow: dict) -> None:
    """In-place: split code template field values from strings to line arrays.

    Converts ``template.<field>.value`` from a single string to a
    ``list[str]`` (one element per line) when the field type is ``"code"``.
    This gives git line-level diffs instead of a single opaque blob.
    """
    for node in flow.get("data", {}).get("nodes", []):
        template = node.get("data", {}).get("node", {}).get("template", {})
        if not isinstance(template, dict):
            continue
        for field_data in template.values():
            if not isinstance(field_data, dict):
                continue
            if field_data.get("type") == "code":
                value = field_data.get("value")
                if isinstance(value, str):
                    # split("\n") — not splitlines() — so that the trailing newline
                    # is preserved as a final empty string, keeping the round-trip
                    # lossless: "\n".join(s.split("\n")) == s for any string s.
                    field_data["value"] = value.split("\n")


def _join_code_from_lines(flow: dict) -> None:
    """In-place: rejoin code template line arrays back to strings.

    Inverse of :func:`_split_code_to_lines`.  Safe to call on flows that
    already use the string format — ``isinstance`` guard means it's a no-op.
    """
    for node in flow.get("data", {}).get("nodes", []):
        template = node.get("data", {}).get("node", {}).get("template", {})
        if not isinstance(template, dict):
            continue
        for field_data in template.values():
            if not isinstance(field_data, dict):
                continue
            if field_data.get("type") == "code":
                value = field_data.get("value")
                if isinstance(value, list):
                    field_data["value"] = "\n".join(value)


def normalize_flow_for_export(flow: dict) -> dict:
    """Return a git-friendly, deterministic copy of a flow dict.

    Applied to every flow before it is written into a download ZIP.

    Transformations
    ---------------
    * Strips volatile top-level fields (``updated_at``, ``created_at``,
      ``user_id``, ``folder_id``, ``access_type``, ``gradient``) — these
      change between instances / users without affecting flow logic.
    * Strips node UI-state fields (``positionAbsolute``, ``dragging``,
      ``selected``) — these change on every canvas interaction.
    * Converts ``template.<field>.value`` strings to ``list[str]`` for
      ``type == "code"`` fields, enabling line-level git diffs.

    Key sorting is handled at serialisation time via
    ``orjson_dumps(sort_keys=True)``.
    """
    import copy

    flow = copy.deepcopy(flow)

    # Strip volatile top-level metadata
    for key in _VOLATILE_TOP_LEVEL:
        flow.pop(key, None)

    # Strip node UI state
    for node in flow.get("data", {}).get("nodes", []):
        for key in _VOLATILE_NODE_FIELDS:
            node.pop(key, None)

    # Code → line arrays
    _split_code_to_lines(flow)

    return flow


def normalize_code_for_import(flow: dict) -> dict:
    """Rejoin code-as-lines back to strings for backward-compatible import.

    Accepts both the list format produced by :func:`normalize_flow_for_export`
    and the legacy single-string format, so this function is safe to call
    unconditionally on every uploaded flow.
    """
    import copy

    flow = copy.deepcopy(flow)
    _join_code_from_lines(flow)
    return flow


def build_input_keys_response(langchain_object, artifacts):
    """Build the input keys response."""
    input_keys_response = {
        "input_keys": dict.fromkeys(langchain_object.input_keys, ""),
        "memory_keys": [],
        "handle_keys": artifacts.get("handle_keys", []),
    }

    # Set the input keys values from artifacts
    for key, value in artifacts.items():
        if key in input_keys_response["input_keys"]:
            input_keys_response["input_keys"][key] = value
    # If the object has memory, that memory will have a memory_variables attribute
    # memory variables should be removed from the input keys
    if hasattr(langchain_object, "memory") and hasattr(langchain_object.memory, "memory_variables"):
        # Remove memory variables from input keys
        input_keys_response["input_keys"] = {
            key: value
            for key, value in input_keys_response["input_keys"].items()
            if key not in langchain_object.memory.memory_variables
        }
        # Add memory variables to memory_keys
        input_keys_response["memory_keys"] = langchain_object.memory.memory_variables

    if hasattr(langchain_object, "prompt") and hasattr(langchain_object.prompt, "template"):
        input_keys_response["template"] = langchain_object.prompt.template

    return input_keys_response


def validate_is_component(flows: list[Flow]) -> list[Flow]:
    """Return flows with ``is_component`` inferred from flow data when unset.

    Note: mutates the ORM instances in-place because SQLAlchemy requires
    mutation for dirty-tracking.  This is an intentional exception to the
    immutability guideline — creating copies would detach them from the session.
    """
    for flow in flows:
        if not flow.data or flow.is_component is not None:
            continue

        is_component = get_is_component_from_data(flow.data)
        if is_component is not None:
            flow.is_component = is_component
        else:
            flow.is_component = len(flow.data.get("nodes", [])) == 1
    return flows


def get_is_component_from_data(data: dict):
    """Returns True if the data is a component."""
    return data.get("is_component")


async def check_langflow_version(component: StoreComponentCreate) -> None:
    from langflow.utils.version import get_version_info

    __version__ = get_version_info()["version"]

    if not component.last_tested_version:
        component.last_tested_version = __version__

    langflow_version = await get_lf_version_from_pypi()
    if langflow_version is None:
        raise HTTPException(status_code=500, detail="Unable to verify the latest version of Langflow")
    if langflow_version != component.last_tested_version:
        await logger.awarning(
            f"Your version of Langflow ({component.last_tested_version}) is outdated. "
            f"Please update to the latest version ({langflow_version}) and try again."
        )


def format_elapsed_time(elapsed_time: float) -> str:
    """Format elapsed time to a human-readable format coming from perf_counter().

    - Less than 1 second: returns milliseconds
    - Less than 1 minute: returns seconds rounded to 1 decimal
    - 1 minute or more: returns minutes and seconds
    """
    delta = timedelta(seconds=elapsed_time)
    if delta < timedelta(seconds=1):
        milliseconds = round(delta / timedelta(milliseconds=1))
        return f"{milliseconds} ms"

    if delta < timedelta(minutes=1):
        seconds = round(elapsed_time, 1)
        unit = "second" if seconds == 1 else "seconds"
        return f"{seconds} {unit}"

    minutes = delta // timedelta(minutes=1)
    seconds = round((delta - timedelta(minutes=minutes)).total_seconds(), 1)
    minutes_unit = "minute" if minutes == 1 else "minutes"
    seconds_unit = "second" if seconds == 1 else "seconds"
    return f"{minutes} {minutes_unit}, {seconds} {seconds_unit}"


def format_syntax_error_message(exc: SyntaxError) -> str:
    """Format a SyntaxError message for returning to the frontend."""
    if exc.text is None:
        return f"Syntax error in code. Error on line {exc.lineno}"
    return f"Syntax error in code. Error on line {exc.lineno}: {exc.text.strip()}"


def get_causing_exception(exc: BaseException) -> BaseException:
    """Get the causing exception from an exception."""
    if hasattr(exc, "__cause__") and exc.__cause__:
        return get_causing_exception(exc.__cause__)
    return exc


def format_exception_message(exc: Exception) -> str:
    """Format an exception message for returning to the frontend."""
    # We need to check if the __cause__ is a SyntaxError
    # If it is, we need to return the message of the SyntaxError
    causing_exception = get_causing_exception(exc)
    if isinstance(causing_exception, SyntaxError):
        return format_syntax_error_message(causing_exception)
    return str(exc)


def get_top_level_vertices(graph, vertices_ids):
    """Retrieves the top-level vertices from the given graph based on the provided vertex IDs.

    Args:
        graph (Graph): The graph object containing the vertices.
        vertices_ids (list): A list of vertex IDs.

    Returns:
        list: A list of top-level vertex IDs.

    """
    top_level_vertices = []
    for vertex_id in vertices_ids:
        vertex = graph.get_vertex(vertex_id)
        if vertex.parent_is_top_level:
            top_level_vertices.append(vertex.parent_node_id)
        else:
            top_level_vertices.append(vertex_id)
    return top_level_vertices


def parse_exception(exc):
    """Parse the exception message."""
    if hasattr(exc, "body"):
        return exc.body["message"]
    return str(exc)


def get_suggestion_message(outdated_components: list[str]) -> str:
    """Get the suggestion message for the outdated components."""
    count = len(outdated_components)
    if count == 0:
        return "The flow contains no outdated components."
    if count == 1:
        return (
            "The flow contains 1 outdated component. "
            f"We recommend updating the following component: {outdated_components[0]}."
        )
    components = ", ".join(outdated_components)
    return (
        f"The flow contains {count} outdated components. We recommend updating the following components: {components}."
    )


def parse_value(value: Any, input_type: str) -> Any:
    """Helper function to parse the value based on input type."""
    if value == "":
        return {} if input_type == "DictInput" else value
    if input_type == "IntInput":
        return int(value) if value is not None else None
    if input_type == "FloatInput":
        return float(value) if value is not None else None
    if input_type == "DictInput":
        if isinstance(value, dict):
            return value
        try:
            parsed = _json.loads(value) if value is not None else {}
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return value


def custom_params(
    page: int | None = Query(None),
    size: int | None = Query(None),
):
    if page is None and size is None:
        return None
    return Params(page=page or MIN_PAGE_SIZE, size=size or MAX_PAGE_SIZE)


def extract_global_variables_from_headers(headers) -> dict[str, str]:
    """Extract global variables from HTTP headers with prefix X-LANGFLOW-GLOBAL-VAR-*.

    Args:
        headers: HTTP headers object (e.g., from FastAPI Request.headers)

    Returns:
        Dictionary mapping variable names (uppercase) to their values

    Example:
        headers = {"X-LANGFLOW-GLOBAL-VAR-API-KEY": "secret", "Content-Type": "application/json"}
        result = extract_global_variables_from_headers(headers)
        # Returns: {"API_KEY": "secret"}
    """
    variables: dict[str, str] = {}

    try:
        for header_name, header_value in headers.items():
            header_lower = header_name.lower()
            if header_lower.startswith(LANGFLOW_GLOBAL_VAR_HEADER_PREFIX):
                var_name = header_lower[len(LANGFLOW_GLOBAL_VAR_HEADER_PREFIX) :].upper()
                variables[var_name] = header_value
    except Exception as exc:  # noqa: BLE001
        # Log the error but don't raise - we want to continue execution
        logger.exception("Failed to extract global variables from headers: %s", exc)

    return variables


def raise_error_if_astra_cloud_env():
    """Raise an error if we're in an Astra cloud environment."""
    try:
        raise_error_if_astra_cloud_disable_component(disable_endpoint_in_astra_cloud_msg)
    except Exception as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
