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


async def load_flow(flow_id: str, tweaks: Optional[dict] = None) -> "Graph":
    from langflow.graph.graph.base import Graph
    from langflow.processing.process import process_tweaks

    with session_scope() as session:
        graph_data = flow.data if (flow := session.get(Flow, flow_id)) else None
    if not graph_data:
        raise ValueError(f"Flow {flow_id} not found")
    if tweaks:
        graph_data = process_tweaks(graph_data=graph_data, tweaks=tweaks)
    graph = Graph.from_payload(graph_data, flow_id=flow_id)
    return graph


async def run_flow(
    inputs: Union[dict, List[dict]] = None,
    flow_id: Optional[str] = None,
    flow_name: Optional[str] = None,
    tweaks: Optional[dict] = None,
    flows_records: Optional[List[Record]] = None,
) -> Any:
    if not flow_id and not flow_name:
        raise ValueError("Flow ID or Flow Name is required")
    if not flows_records:
        flows_records = list_flows()
    if not flow_id and flows_records:
        flow_ids = [flow.data["id"] for flow in flows_records if flow.data["name"] == flow_name]
        if not flow_ids:
            raise ValueError(f"Flow {flow_name} not found")
        elif len(flow_ids) > 1:
            raise ValueError(f"Multiple flows found with the name {flow_name}")
        flow_id = flow_ids[0]

    if not flow_id:
        raise ValueError(f"Flow {flow_name} not found")
    graph = await load_flow(flow_id, tweaks)

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
