import dataclasses
import os
import uuid
from typing import Optional, Any

from astrapy.admin import parse_api_endpoint

from langflow.api.v1.schemas import InputValueRequest
from langflow.custom import Component
from langflow.field_typing import Embeddings
from langflow.graph import Graph
from langflow.processing.process import run_graph_internal
import requests


def check_env_vars(*vars):
    """
    Check if all specified environment variables are set.

    Args:
    *vars (str): The environment variables to check.

    Returns:
    bool: True if all environment variables are set, False otherwise.
    """
    return all(os.getenv(var) for var in vars)


def valid_nvidia_vectorize_region(api_endpoint: str) -> bool:
    """
    Check if the specified region is valid.

    Args:
    region (str): The region to check.

    Returns:
    bool: True if the region is contains hosted nvidia models, False otherwise.
    """
    parsed_endpoint = parse_api_endpoint(api_endpoint)
    if not parsed_endpoint:
        raise ValueError("Invalid ASTRA_DB_API_ENDPOINT")
    return parsed_endpoint.region in ["us-east-2"]


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
        result = []
        for node in self.json["data"]["nodes"]:
            if node["data"]["type"] == component_type:
                result.append(node["id"])
        if not result:
            raise ValueError(
                f"Component of type {component_type} not found, available types: {', '.join(set(node['data']['type'] for node in self.json['data']['nodes']))}"
            )
        return result

    def get_component_by_type(self, component_type):
        components = self.get_components_by_type(component_type)
        if len(components) > 1:
            raise ValueError(f"Multiple components of type {component_type} found")
        return components[0]

    def set_value(self, component_id, key, value):
        done = False
        for node in self.json["data"]["nodes"]:
            if node["id"] == component_id:
                if key not in node["data"]["node"]["template"]:
                    raise ValueError(f"Component {component_id} does not have input {key}")
                node["data"]["node"]["template"][key]["value"] = value
                node["data"]["node"]["template"][key]["load_from_db"] = False
                done = True
                break
        if not done:
            raise ValueError(f"Component {component_id} not found")


def download_flow_from_github(name: str, version: str) -> JSONFlow:
    response = requests.get(
        f"https://raw.githubusercontent.com/langflow-ai/langflow/v{version}/src/backend/base/langflow/initial_setup/starter_projects/{name}.json"
    )
    response.raise_for_status()
    as_json = response.json()
    return JSONFlow(json=as_json)


async def run_json_flow(
    json_flow: JSONFlow, run_input: Optional[Any] = None, session_id: Optional[str] = None
) -> dict[str, Any]:
    graph = Graph.from_payload(json_flow.json)
    return await run_flow(graph, run_input, session_id)


async def run_flow(graph: Graph, run_input: Optional[Any] = None, session_id: Optional[str] = None) -> dict[str, Any]:
    graph.prepare()
    if run_input:
        graph_run_inputs = [InputValueRequest(input_value=run_input, type="chat")]
    else:
        graph_run_inputs = []

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
    inputs: dict = None,
    run_input: Optional[Any] = None,
    session_id: Optional[str] = None,
    input_type: Optional[str] = "chat",
) -> dict[str, Any]:
    user_id = str(uuid.uuid4())
    flow_id = str(uuid.uuid4())
    graph = Graph(user_id=user_id, flow_id=flow_id)

    def _add_component(clazz: type, inputs: Optional[dict] = None) -> str:
        raw_inputs = {}
        if inputs:
            for key, value in inputs.items():
                if not isinstance(value, ComponentInputHandle):
                    raw_inputs[key] = value
                if isinstance(value, Component):
                    raise ValueError("Component inputs must be wrapped in ComponentInputHandle")
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
    if run_input:
        graph_run_inputs = [InputValueRequest(input_value=run_input, type=input_type)]
    else:
        graph_run_inputs = []

    _, _ = await run_graph_internal(
        graph, flow_id, session_id=session_id, inputs=graph_run_inputs, outputs=[component_id]
    )
    return graph.get_vertex(component_id)._built_object
