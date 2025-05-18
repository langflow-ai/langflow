from langflow_execution.api.v1.schema.flow import Flow, FlowExecutionRequest
from langflow_execution.events.event_manager import EventManager

from langflow_execution.graph.schema import RunOutputs
from langflow_execution.graph.graph.base import Graph

async def simple_run_flow(
    flow: Flow,
    input_request: FlowExecutionRequest,
    *,
    stream: bool = False,
    event_manager: EventManager | None = None,
):
    try:
        task_result: list[RunOutputs] = []
        flow_id_str = str(flow.id)

        # copy the flow data to avoid modifying the original data
        graph_data = flow.data.copy()

        graph = Graph.from_payload(graph_data, flow_id=flow_id_str, user_id=None, flow_name=flow.name) # TODO: user_id
        inputs = None
        if input_request.input_value is not None:
            inputs = [
                InputValueRequest(
                    components=[],
                    input_value=input_request.input_value,
                    type=input_request.input_type,
                )
            ]
        if input_request.output_component:
            outputs = [input_request.output_component]
        else:
            outputs = [
                vertex.id
                for vertex in graph.vertices
                if input_request.output_type == "debug"
                or (
                    vertex.is_output
                    and (input_request.output_type == "any" or input_request.output_type in vertex.id.lower())  # type: ignore[operator]
                )
            ]
        task_result, session_id = await run_graph_internal(
            graph=graph,
            flow_id=flow_id_str,
            session_id=input_request.session_id,
            inputs=inputs,
            outputs=outputs,
            stream=stream,
            event_manager=event_manager,
        )

        return RunResponse(outputs=task_result, session_id=session_id)

    except sa.exc.StatementError as exc:
        raise ValueError(str(exc)) from exc    

        
async def simple_run_flow_task(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    stream: bool = False,
    api_key_user: User | None = None,
    event_manager: EventManager | None = None,
):
    """Run a flow task as a BackgroundTask, therefore it should not throw exceptions."""
    try:
        return await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=stream,
            api_key_user=api_key_user,
            event_manager=event_manager,
        )

    except Exception:  # noqa: BLE001
        logger.exception(f"Error running flow {flow.id} task")

