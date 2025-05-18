from langflow_execution.graph.execution.schema import Flow, FlowExecutionRequest, InputValueRequest
from langflow_execution.events.event_manager import EventManager
from langflow_execution.graph.graph.base import Graph
from langflow_execution.graph.schema import InputValue, RunOutputs, RunResponse
from langflow_execution.services.manager import ServiceManager

from loguru import logger
import sqlalchemy as sa

INPUT_FIELD_NAME = "input_value"

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
    input_request: FlowExecutionRequest,
    *,
    stream: bool = False,
    event_manager: EventManager | None = None,
):
    """Run a flow task as a BackgroundTask, therefore it should not throw exceptions."""
    try:
        return await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=stream,
            event_manager=event_manager,
        )

    except Exception:  # noqa: BLE001
        logger.exception(f"Error running flow {flow.id} task")


async def run_graph(
    graph: Graph,
    input_value: str,
    input_type: str,
    output_type: str,
    *,
    session_id: str | None = None,
    fallback_to_env_vars: bool = False,
    output_component: str | None = None,
    stream: bool = False,
) -> list[RunOutputs]:
    """Runs the given Langflow Graph with the specified input and returns the outputs.

    Args:
        graph (Graph): The graph to be executed.
        input_value (str): The input value to be passed to the graph.
        input_type (str): The type of the input value.
        output_type (str): The type of the desired output.
        session_id (str | None, optional): The session ID to be used for the flow. Defaults to None.
        fallback_to_env_vars (bool, optional): Whether to fallback to environment variables.
            Defaults to False.
        output_component (Optional[str], optional): The specific output component to retrieve. Defaults to None.
        stream (bool, optional): Whether to stream the results or not. Defaults to False.

    Returns:
        List[RunOutputs]: A list of RunOutputs objects representing the outputs of the graph.

    """
    inputs = [InputValue(components=[], input_value=input_value, type=input_type)]
    if output_component:
        outputs = [output_component]
    else:
        outputs = [
            vertex.id
            for vertex in graph.vertices
            if output_type == "debug"
            or (vertex.is_output and (output_type == "any" or output_type in vertex.id.lower()))
        ]
    components = []
    inputs_list = []
    types = []
    for input_value_request in inputs:
        if input_value_request.input_value is None:
            logger.warning("InputValueRequest input_value cannot be None, defaulting to an empty string.")
            input_value_request.input_value = ""
        components.append(input_value_request.components or [])
        inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value})
        types.append(input_value_request.type)
    return await graph.arun(
        inputs_list,
        inputs_components=components,
        types=types,
        outputs=outputs or [],
        stream=stream,
        session_id=session_id,
        fallback_to_env_vars=fallback_to_env_vars,
    )


async def run_graph_internal(
    graph: Graph,
    flow_id: str,
    *,
    stream: bool = False,
    session_id: str | None = None,
    inputs: list[InputValueRequest] | None = None,
    outputs: list[str] | None = None,
    event_manager: EventManager | None = None,
) -> tuple[list[RunOutputs], str]:
    """Run the graph and generate the result."""
    inputs = inputs or []
    effective_session_id = session_id or flow_id
    components = []
    inputs_list = []
    types = []
    for input_value_request in inputs:
        if input_value_request.input_value is None:
            logger.warning("InputValueRequest input_value cannot be None, defaulting to an empty string.")
            input_value_request.input_value = ""
        components.append(input_value_request.components or [])
        inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value})
        types.append(input_value_request.type)

    fallback_to_env_vars = ServiceManager.get_instance().get_settings_service().settings.fallback_to_env_vars
    graph.session_id = effective_session_id
    run_outputs = await graph.arun(
        inputs=inputs_list,
        inputs_components=components,
        types=types,
        outputs=outputs or [],
        stream=stream,
        session_id=effective_session_id or "",
        fallback_to_env_vars=fallback_to_env_vars,
        event_manager=event_manager,
    )
    return run_outputs, effective_session_id

