import dataclasses
import os
import uuid
from typing import Any

import pytest
import requests
from astrapy.admin import parse_api_endpoint
from langflow.api.v1.schemas import InputValueRequest
from langflow.custom import Component
from langflow.field_typing import Embeddings
from langflow.processing.process import run_graph_internal

from lfx.custom.eval import eval_custom_component_code
from lfx.graph import Graph


def check_env_vars(*env_vars):
    """Check if all specified environment variables are set.

    Args:
    *env_vars (str): The environment variables to check.

    Returns:
    bool: True if all environment variables are set, False otherwise.
    """
    return all(os.getenv(var) for var in env_vars)


def valid_nvidia_vectorize_region(api_endpoint: str) -> bool:
    """Check if the specified region is valid.

    Args:
        api_endpoint: The API endpoint to check.

    Returns:
        True if the region contains hosted nvidia models, False otherwise.
    """
    parsed_endpoint = parse_api_endpoint(api_endpoint)
    if not parsed_endpoint:
        msg = "Invalid ASTRA_DB_API_ENDPOINT"
        raise ValueError(msg)
    return parsed_endpoint.region == "us-east-2"


class MockEmbeddings(Embeddings):
    def __init__(self):
        self.embedded_documents = None
        self.embedded_query = None

    @staticmethod
    def mock_embedding(text: str):
        return [len(text) / 2, len(text) / 5, len(text) / 10]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embedded_documents = texts
        return [self.mock_embedding(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.embedded_query = text
        return self.mock_embedding(text)


@dataclasses.dataclass
class JSONFlow:
    json: dict

    def get_components_by_type(self, component_type):
        result = [node["id"] for node in self.json["data"]["nodes"] if node["data"]["type"] == component_type]
        if not result:
            msg = (
                f"Component of type {component_type} not found, "
                f"available types: {', '.join({node['data']['type'] for node in self.json['data']['nodes']})}"
            )
            raise ValueError(msg)
        return result

    def get_component_by_type(self, component_type):
        components = self.get_components_by_type(component_type)
        if len(components) > 1:
            msg = f"Multiple components of type {component_type} found"
            raise ValueError(msg)
        return components[0]

    def set_value(self, component_id, key, value):
        done = False
        for node in self.json["data"]["nodes"]:
            if node["id"] == component_id:
                if key not in node["data"]["node"]["template"]:
                    msg = f"Component {component_id} does not have input {key}"
                    raise ValueError(msg)
                node["data"]["node"]["template"][key]["value"] = value
                node["data"]["node"]["template"][key]["load_from_db"] = False
                done = True
                break
        if not done:
            msg = f"Component {component_id} not found"
            raise ValueError(msg)


def download_flow_from_github(name: str, version: str) -> JSONFlow:
    response = requests.get(
        f"https://raw.githubusercontent.com/langflow-ai/langflow/v{version}/src/backend/base/langflow/initial_setup/starter_projects/{name}.json",
        timeout=10,
    )
    response.raise_for_status()
    as_json = response.json()
    return JSONFlow(json=as_json)


def download_component_from_github(module: str, file_name: str, version: str) -> Component:
    version_string = f"v{version}" if version != "main" else version
    response = requests.get(
        f"https://raw.githubusercontent.com/langflow-ai/langflow/{version_string}/src/backend/base/langflow/components/{module}/{file_name}.py",
        timeout=10,
    )
    response.raise_for_status()
    return Component(_code=response.text)


async def run_json_flow(
    json_flow: JSONFlow, run_input: Any | None = None, session_id: str | None = None
) -> dict[str, Any]:
    graph = Graph.from_payload(json_flow.json)
    return await run_flow(graph, run_input, session_id)


async def run_flow(graph: Graph, run_input: Any | None = None, session_id: str | None = None) -> dict[str, Any]:
    graph.prepare()
    graph_run_inputs = [InputValueRequest(input_value=run_input, type="chat")] if run_input else []

    flow_id = str(uuid.uuid4())

    results, _ = await run_graph_internal(graph, flow_id, session_id=session_id, inputs=graph_run_inputs)
    outputs = {}
    for r in results:
        for out in r.outputs:
            outputs |= out.results
    return outputs


@dataclasses.dataclass
class ComponentInputHandle:
    clazz: type
    inputs: dict
    output_name: str


async def run_single_component(
    clazz: type,
    inputs: dict | None = None,
    run_input: Any | None = None,
    session_id: str | None = None,
    input_type: str | None = "chat",
) -> dict[str, Any]:
    user_id = str(uuid.uuid4())
    flow_id = str(uuid.uuid4())
    graph = Graph(user_id=user_id, flow_id=flow_id)

    def _add_component(clazz: type, inputs: dict | None = None) -> str:
        raw_inputs = {}
        if inputs:
            for key, value in inputs.items():
                if not isinstance(value, ComponentInputHandle):
                    raw_inputs[key] = value
                if isinstance(value, Component):
                    msg = "Component inputs must be wrapped in ComponentInputHandle"
                    raise TypeError(msg)
        component = clazz(**raw_inputs, _user_id=user_id)
        component_id = graph.add_component(component)
        if inputs:
            for input_name, handle in inputs.items():
                if isinstance(handle, ComponentInputHandle):
                    handle_component_id = _add_component(handle.clazz, handle.inputs)
                    graph.add_component_edge(handle_component_id, (handle.output_name, input_name), component_id)
        return component_id

    component_id = _add_component(clazz, inputs)
    graph.prepare()
    graph_run_inputs = [InputValueRequest(input_value=run_input, type=input_type)] if run_input else []

    _, _ = await run_graph_internal(
        graph, flow_id, session_id=session_id, inputs=graph_run_inputs, outputs=[component_id]
    )
    return graph.get_vertex(component_id).built_object


def build_component_instance_for_tests(version: str, module: str, file_name: str, **kwargs):
    component = download_component_from_github(module, file_name, version)
    cc_class = eval_custom_component_code(component._code)
    return cc_class(**kwargs), component._code


def pyleak_marker(**extra_args):
    default_args = {
        "enable_task_creation_tracking": True,  # log task creation stacks
        "thread_name_filter": r"^(?!asyncio_\d+$).*",  # exclude `asyncio_{num}` threads
    }
    return pytest.mark.no_leaks(**default_args, **extra_args)
