import uuid
import warnings
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from sqlmodel import Session

from langflow.graph.graph.base import Graph
from langflow.services.chat.service import ChatService
from langflow.services.database.models.flow import Flow
from langflow.services.store.schema import StoreComponentCreate
from langflow.services.store.utils import get_lf_version_from_pypi

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow


API_WORDS = ["api", "key", "token"]


def has_api_terms(word: str):
    return "api" in word and ("key" in word or ("token" in word and "tokens" not in word))


def remove_api_keys(flow: dict):
    """Remove api keys from flow data."""
    if flow.get("data") and flow["data"].get("nodes"):
        for node in flow["data"]["nodes"]:
            node_data = node.get("data").get("node")
            template = node_data.get("template")
            for value in template.values():
                if isinstance(value, dict) and has_api_terms(value["name"]) and value.get("password"):
                    value["value"] = None

    return flow


def build_input_keys_response(langchain_object, artifacts):
    """Build the input keys response."""

    input_keys_response = {
        "input_keys": {key: "" for key in langchain_object.input_keys},
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


def validate_is_component(flows: list["Flow"]):
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


async def check_langflow_version(component: StoreComponentCreate):
    from langflow.utils.version import get_version_info

    __version__ = get_version_info()["version"]

    if not component.last_tested_version:
        component.last_tested_version = __version__

    langflow_version = get_lf_version_from_pypi()
    if langflow_version is None:
        raise HTTPException(status_code=500, detail="Unable to verify the latest version of Langflow")
    elif langflow_version != component.last_tested_version:
        warnings.warn(
            f"Your version of Langflow ({component.last_tested_version}) is outdated. "
            f"Please update to the latest version ({langflow_version}) and try again."
        )


def format_elapsed_time(elapsed_time: float) -> str:
    """Format elapsed time to a human-readable format coming from perf_counter().

    - Less than 1 second: returns milliseconds
    - Less than 1 minute: returns seconds rounded to 2 decimals
    - 1 minute or more: returns minutes and seconds
    """
    if elapsed_time < 1:
        milliseconds = int(round(elapsed_time * 1000))
        return f"{milliseconds} ms"
    elif elapsed_time < 60:
        seconds = round(elapsed_time, 2)
        unit = "second" if seconds == 1 else "seconds"
        return f"{seconds} {unit}"
    else:
        minutes = int(elapsed_time // 60)
        seconds = round(elapsed_time % 60, 2)
        minutes_unit = "minute" if minutes == 1 else "minutes"
        seconds_unit = "second" if seconds == 1 else "seconds"
        return f"{minutes} {minutes_unit}, {seconds} {seconds_unit}"


async def build_graph_from_data(flow_id: str, payload: dict, **kwargs):
    """Build and cache the graph."""
    graph = Graph.from_payload(payload, flow_id, **kwargs)
    for vertex_id in graph._has_session_id_vertices:
        vertex = graph.get_vertex(vertex_id)
        if vertex is None:
            raise ValueError(f"Vertex {vertex_id} not found")
        if not vertex._raw_params.get("session_id"):
            vertex.update_raw_params({"session_id": flow_id}, overwrite=True)

    run_id = uuid.uuid4()
    graph.set_run_id(run_id)
    graph.set_run_name()
    await graph.initialize_run()
    return graph


async def build_graph_from_db_no_cache(flow_id: str, session: Session):
    """Build and cache the graph."""
    flow: Flow | None = session.get(Flow, flow_id)
    if not flow or not flow.data:
        raise ValueError("Invalid flow ID")
    return await build_graph_from_data(flow_id, flow.data, flow_name=flow.name, user_id=str(flow.user_id))


async def build_graph_from_db(flow_id: str, session: Session, chat_service: "ChatService"):
    graph = await build_graph_from_db_no_cache(flow_id, session)
    await chat_service.set_cache(flow_id, graph)
    return graph


async def build_and_cache_graph_from_data(
    flow_id: str,
    chat_service: "ChatService",
    graph_data: dict,
):  # -> Graph | Any:
    """Build and cache the graph."""
    graph = Graph.from_payload(graph_data, flow_id)
    await chat_service.set_cache(flow_id, graph)
    return graph


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
    """
    Retrieves the top-level vertices from the given graph based on the provided vertex IDs.

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
    elif count == 1:
        return f"The flow contains 1 outdated component. We recommend updating the following component: {outdated_components[0]}."
    else:
        components = ", ".join(outdated_components)
        return f"The flow contains {count} outdated components. We recommend updating the following components: {components}."


def parse_value(value: Any, input_type: str) -> Any:
    """Helper function to parse the value based on input type."""
    if value == "":
        return value
    elif input_type == "IntInput":
        return int(value) if value is not None else None
    elif input_type == "FloatInput":
        return float(value) if value is not None else None
    else:
        return value
