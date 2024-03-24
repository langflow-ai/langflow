from typing import TYPE_CHECKING, Any, List, Optional, Union

from sqlmodel import select

from langflow.schema.schema import INPUT_FIELD_NAME, Record
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope

if TYPE_CHECKING:
    from langflow.graph.graph.base import Graph


def list_flows(*, user_id: Optional[str] = None) -> List[Record]:
    if not user_id:
        raise ValueError("Session is invalid")
    try:
        with session_scope() as session:
            flows = session.exec(
                select(Flow).where(Flow.user_id == user_id).where(Flow.is_component == False)  # noqa
            ).all()

            flows_records = [flow.to_record() for flow in flows]
            return flows_records
    except Exception as e:
        raise ValueError(f"Error listing flows: {e}")


async def load_flow(
    user_id: str, flow_id: Optional[str] = None, flow_name: Optional[str] = None, tweaks: Optional[dict] = None
) -> "Graph":
    from langflow.graph.graph.base import Graph
    from langflow.processing.process import process_tweaks

    if not flow_id and not flow_name:
        raise ValueError("Flow ID or Flow Name is required")
    if not flow_id and flow_name:
        flow_id = find_flow(flow_name, user_id)
        if not flow_id:
            raise ValueError(f"Flow {flow_name} not found")

    with session_scope() as session:
        graph_data = flow.data if (flow := session.get(Flow, flow_id)) else None
    if not graph_data:
        raise ValueError(f"Flow {flow_id} not found")
    if tweaks:
        graph_data = process_tweaks(graph_data=graph_data, tweaks=tweaks)
    graph = Graph.from_payload(graph_data, flow_id=flow_id)
    return graph


def find_flow(flow_name: str, user_id: str) -> Optional[str]:
    with session_scope() as session:
        flow = session.exec(select(Flow).where(Flow.name == flow_name).where(Flow.user_id == user_id)).first()
        return flow.id if flow else None


async def run_flow(
    inputs: Union[dict, List[dict]] = None,
    tweaks: Optional[dict] = None,
    flow_id: Optional[str] = None,
    flow_name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Any:
    graph = await load_flow(user_id, flow_id, flow_name, tweaks)

    if inputs is None:
        inputs = []
    inputs_list = []
    inputs_components = []
    types = []
    for input_dict in inputs:
        inputs_list.append({INPUT_FIELD_NAME: input_dict.get("input_value")})
        inputs_components.append(input_dict.get("components", []))
        types.append(input_dict.get("type", []))

    return await graph.arun(inputs_list, inputs_components=inputs_components, types=types)


def extract_argument_signatures(arguments):
    """
    Extracts and formats function argument signatures with type hints.
    """
    type_mapping = {"str": "str"}  # Extend this mapping as needed.
    return [
        f"{arg['display_name'].replace(' ', '_').lower()}: {type_mapping.get(arg['type'], 'Any')}" for arg in arguments
    ]


def create_function_definition(arg_signatures, body):
    """
    Constructs the function definition string.
    """
    func_signature = ", ".join(arg_signatures)
    return f"def dynamic_function({func_signature}):\n{body}"


def define_dynamic_function(function_definition):
    """
    Defines the dynamic function by executing the function definition string
    within a local environment and returns the function object.
    """
    local_env = {}
    exec(function_definition, globals(), local_env)
    return local_env["dynamic_function"]
