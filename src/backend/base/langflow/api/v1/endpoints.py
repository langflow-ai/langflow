import time
from asyncio import Lock
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, List, Optional, Union
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, UploadFile, status
from loguru import logger
from sqlmodel import Session, select

from langflow.api.v1.schemas import (
    ConfigResponse,
    CustomComponentRequest,
    CustomComponentResponse,
    InputValueRequest,
    ProcessResponse,
    RunResponse,
    SimplifiedAPIRequest,
    TaskStatusResponse,
    UpdateCustomComponentRequest,
    UploadFileResponse,
)
from langflow.custom.custom_component.component import Component
from langflow.custom.utils import build_custom_component_template, get_instance_name
from langflow.exceptions.api import InvalidChatInputException
from langflow.graph.graph.base import Graph
from langflow.graph.schema import RunOutputs
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.interface.initialize.loading import update_params_with_load_from_db_fields
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.schema.graph import Tweaks
from langflow.services.auth.utils import api_key_security, get_current_active_user
from langflow.services.cache.utils import save_uploaded_file
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.flow.utils import get_all_webhook_components_in_flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import (
    get_cache_service,
    get_session,
    get_session_service,
    get_settings_service,
    get_task_service,
    get_telemetry_service,
)
from langflow.services.session.service import SessionService
from langflow.services.task.service import TaskService
from langflow.services.telemetry.schema import RunPayload
from langflow.services.telemetry.service import TelemetryService
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from langflow.services.cache.base import CacheService
    from langflow.services.settings.service import SettingsService

router = APIRouter(tags=["Base"])


@router.get("/all", dependencies=[Depends(get_current_active_user)])
async def get_all(
    settings_service=Depends(get_settings_service),
    cache_service: "CacheService" = Depends(dependency=get_cache_service),
    force_refresh: bool = False,
):
    from langflow.interface.types import get_and_cache_all_types_dict

    try:
        async with Lock() as lock:
            all_types_dict = await get_and_cache_all_types_dict(
                settings_service=settings_service, cache_service=cache_service, force_refresh=force_refresh, lock=lock
            )

            return all_types_dict
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def validate_input_and_tweaks(input_request: SimplifiedAPIRequest):
    # If the input_value is not None and the input_type is "chat"
    # then we need to check the tweaks if the ChatInput component is present
    # and if its input_value is not None
    # if so, we raise an error
    if input_request.tweaks is None:
        return
    for key, value in input_request.tweaks.items():
        if "ChatInput" in key or "Chat Input" in key:
            if isinstance(value, dict):
                has_input_value = value.get("input_value") is not None
                input_value_is_chat = input_request.input_value is not None and input_request.input_type == "chat"
                if has_input_value and input_value_is_chat:
                    raise InvalidChatInputException(
                        "If you pass an input_value to the chat input, you cannot pass a tweak with the same name."
                    )
        elif "Text Input" in key or "TextInput" in key:
            if isinstance(value, dict):
                has_input_value = value.get("input_value") is not None
                input_value_is_text = input_request.input_value is not None and input_request.input_type == "text"
                if has_input_value and input_value_is_text:
                    raise InvalidChatInputException(
                        "If you pass an input_value to the text input, you cannot pass a tweak with the same name."
                    )


async def simple_run_flow(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    stream: bool = False,
    api_key_user: Optional[User] = None,
):
    if input_request.input_value is not None and input_request.tweaks is not None:
        validate_input_and_tweaks(input_request)
    try:
        task_result: List[RunOutputs] = []
        user_id = api_key_user.id if api_key_user else None
        flow_id_str = str(flow.id)
        if flow.data is None:
            raise ValueError(f"Flow {flow_id_str} has no data")
        graph_data = flow.data.copy()
        graph_data = process_tweaks(graph_data, input_request.tweaks or {}, stream=stream)
        graph = Graph.from_payload(graph_data, flow_id=flow_id_str, user_id=str(user_id), flow_name=flow.name)
        inputs = [
            InputValueRequest(components=[], input_value=input_request.input_value, type=input_request.input_type)
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
                    and (input_request.output_type == "any" or input_request.output_type in vertex.id.lower())  # type: ignore
                )
            ]
        task_result, session_id = await run_graph_internal(
            graph=graph,
            flow_id=flow_id_str,
            session_id=input_request.session_id,
            inputs=inputs,
            outputs=outputs,
            stream=stream,
        )

        return RunResponse(outputs=task_result, session_id=session_id)

    except sa.exc.StatementError as exc:
        raise ValueError(str(exc)) from exc


async def simple_run_flow_task(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    stream: bool = False,
    api_key_user: Optional[User] = None,
):
    """
    Run a flow task as a BackgroundTask, therefore it should not throw exceptions.
    """
    try:
        result = await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=stream,
            api_key_user=api_key_user,
        )
        return result

    except Exception as exc:
        logger.exception(f"Error running flow {flow.id} task: {exc}")


@router.post("/run/{flow_id_or_name}", response_model=RunResponse, response_model_exclude_none=True)
async def simplified_run_flow(
    background_tasks: BackgroundTasks,
    flow: Annotated[Flow, Depends(get_flow_by_id_or_endpoint_name)],
    input_request: SimplifiedAPIRequest = SimplifiedAPIRequest(),
    stream: bool = False,
    api_key_user: User = Depends(api_key_security),
    telemetry_service: "TelemetryService" = Depends(get_telemetry_service),
):
    """
    Executes a specified flow by ID with input customization, performance enhancements through caching, and optional data streaming.

    ### Parameters:
    - `db` (Session): Database session for executing queries.
    - `flow_id_or_name` (str): ID or endpoint name of the flow to run.
    - `input_request` (SimplifiedAPIRequest): Request object containing input values, types, output selection, tweaks, and session ID.
    - `api_key_user` (User): User object derived from the provided API key, used for authentication.
    - `session_service` (SessionService): Service for managing flow sessions, essential for session reuse and caching.

    ### SimplifiedAPIRequest:
    - `input_value` (Optional[str], default=""): Input value to pass to the flow.
    - `input_type` (Optional[Literal["chat", "text", "any"]], default="chat"): Type of the input value, determining how the input is interpreted.
    - `output_type` (Optional[Literal["chat", "text", "any", "debug"]], default="chat"): Desired type of output, affecting which components' outputs are included in the response. If set to "debug", all outputs are returned.
    - `output_component` (Optional[str], default=None): Specific component output to retrieve. If provided, only the output of the specified component is returned. This overrides the `output_type` parameter.
    - `tweaks` (Optional[Tweaks], default=None): Adjustments to the flow's behavior, allowing for custom execution parameters.
    - `session_id` (Optional[str], default=None): An identifier for reusing session data, aiding in performance for subsequent requests.


    ### Tweaks
    A dictionary of tweaks to customize the flow execution. The tweaks can be used to modify the flow's parameters and components. Tweaks can be overridden by the input values.
    You can use Component's `id` or Display Name as key to tweak a specific component (e.g., `{"Component Name": {"parameter_name": "value"}}`).
    You can also use the parameter name as key to tweak all components with that parameter (e.g., `{"parameter_name": "value"}`).

    ### Returns:
    - A `RunResponse` object containing the execution results, including selected (or all, based on `output_type`) outputs of the flow and the session ID, facilitating result retrieval and further interactions in a session context.

    ### Raises:
    - HTTPException: 404 if the specified flow ID curl -X 'POST' \

    ### Example:
    ```bash
    curl -X 'POST' \
      'http://<your_server>/run/{flow_id}' \
      -H 'accept: application/json' \
      -H 'Content-Type: application/json' \
      -H 'x-api-key: YOU_API_KEY' \
      -H '
      -d '{
            "input_value": "Sample input",
            "input_type": "chat",
            "output_type": "chat",
            "tweaks": {},
          }'
    ```

    This endpoint provides a powerful interface for executing flows with enhanced flexibility and efficiency, supporting a wide range of applications by allowing for dynamic input and output configuration along with performance optimizations through session management and caching.
    """
    start_time = time.perf_counter()
    try:
        result = await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=stream,
            api_key_user=api_key_user,
        )
        end_time = time.perf_counter()
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(runIsWebhook=False, runSeconds=int(end_time - start_time), runSuccess=True, runErrorMessage=""),
        )
        return result

    except ValueError as exc:
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                runIsWebhook=False,
                runSeconds=int(time.perf_counter() - start_time),
                runSuccess=False,
                runErrorMessage=str(exc),
            ),
        )
        if "badly formed hexadecimal UUID string" in str(exc):
            # This means the Flow ID is not a valid UUID which means it can't find the flow
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if "not found" in str(exc):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        else:
            logger.exception(exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except InvalidChatInputException as exc:
        logger.error(exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(exc)
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                runIsWebhook=False,
                runSeconds=int(time.perf_counter() - start_time),
                runSuccess=False,
                runErrorMessage=str(exc),
            ),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/webhook/{flow_id_or_name}", response_model=dict, status_code=HTTPStatus.ACCEPTED)
async def webhook_run_flow(
    flow: Annotated[Flow, Depends(get_flow_by_id_or_endpoint_name)],
    request: Request,
    background_tasks: BackgroundTasks,
    telemetry_service: "TelemetryService" = Depends(get_telemetry_service),
):
    """
    Run a flow using a webhook request.

    Args:
        db (Session): The database session.
        request (Request): The incoming HTTP request.
        background_tasks (BackgroundTasks): The background tasks manager.
        session_service (SessionService, optional): The session service. Defaults to Depends(get_session_service).
        flow (Flow, optional): The flow to be executed. Defaults to Depends(get_flow_by_id).

    Returns:
        dict: A dictionary containing the status of the task.

    Raises:
        HTTPException: If the flow is not found or if there is an error processing the request.
    """
    try:
        start_time = time.perf_counter()
        logger.debug("Received webhook request")
        data = await request.body()
        if not data:
            logger.error("Request body is empty")
            raise ValueError(
                "Request body is empty. You should provide a JSON payload containing the flow ID.",
            )

        # get all webhook components in the flow
        webhook_components = get_all_webhook_components_in_flow(flow.data)
        tweaks = {}

        for component in webhook_components:
            tweaks[component["id"]] = {"data": data.decode() if isinstance(data, bytes) else data}
        input_request = SimplifiedAPIRequest(
            input_value="",
            input_type="chat",
            output_type="chat",
            tweaks=tweaks,
            session_id=None,
        )
        logger.debug("Starting background task")
        background_tasks.add_task(  # type: ignore
            simple_run_flow_task,
            flow=flow,
            input_request=input_request,
        )
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                runIsWebhook=True, runSeconds=int(time.perf_counter() - start_time), runSuccess=True, runErrorMessage=""
            ),
        )
        return {"message": "Task started in the background", "status": "in progress"}
    except Exception as exc:
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                runIsWebhook=True,
                runSeconds=int(time.perf_counter() - start_time),
                runSuccess=False,
                runErrorMessage=str(exc),
            ),
        )
        if "Flow ID is required" in str(exc) or "Request body is empty" in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/run/advanced/{flow_id}", response_model=RunResponse, response_model_exclude_none=True)
async def experimental_run_flow(
    session: Annotated[Session, Depends(get_session)],
    flow_id: UUID,
    inputs: Optional[List[InputValueRequest]] = [InputValueRequest(components=[], input_value="")],
    outputs: Optional[List[str]] = [],
    tweaks: Annotated[Optional[Tweaks], Body(embed=True)] = None,  # noqa: F821
    stream: Annotated[bool, Body(embed=True)] = False,  # noqa: F821
    session_id: Annotated[Union[None, str], Body(embed=True)] = None,  # noqa: F821
    api_key_user: User = Depends(api_key_security),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Executes a specified flow by ID with optional input values, output selection, tweaks, and streaming capability.
    This endpoint supports running flows with caching to enhance performance and efficiency.

    ### Parameters:
    - `flow_id` (str): The unique identifier of the flow to be executed.
    - `inputs` (List[InputValueRequest], optional): A list of inputs specifying the input values and components for the flow. Each input can target specific components and provide custom values.
    - `outputs` (List[str], optional): A list of output names to retrieve from the executed flow. If not provided, all outputs are returned.
    - `tweaks` (Optional[Tweaks], optional): A dictionary of tweaks to customize the flow execution. The tweaks can be used to modify the flow's parameters and components. Tweaks can be overridden by the input values.
    - `stream` (bool, optional): Specifies whether the results should be streamed. Defaults to False.
    - `session_id` (Union[None, str], optional): An optional session ID to utilize existing session data for the flow execution.
    - `api_key_user` (User): The user associated with the current API key. Automatically resolved from the API key.
    - `session_service` (SessionService): The session service object for managing flow sessions.

    ### Returns:
    A `RunResponse` object containing the selected outputs (or all if not specified) of the executed flow and the session ID. The structure of the response accommodates multiple inputs, providing a nested list of outputs for each input.

    ### Raises:
    HTTPException: Indicates issues with finding the specified flow, invalid input formats, or internal errors during flow execution.

    ### Example usage:
    ```json
    POST /run/{flow_id}
    x-api-key: YOUR_API_KEY
    Payload:
    {
        "inputs": [
            {"components": ["component1"], "input_value": "value1"},
            {"components": ["component3"], "input_value": "value2"}
        ],
        "outputs": ["Component Name", "component_id"],
        "tweaks": {"parameter_name": "value", "Component Name": {"parameter_name": "value"}, "component_id": {"parameter_name": "value"}}
        "stream": false
    }
    ```

    This endpoint facilitates complex flow executions with customized inputs, outputs, and configurations, catering to diverse application requirements.
    """
    try:
        flow_id_str = str(flow_id)
        if outputs is None:
            outputs = []

        artifacts = {}
        if session_id:
            session_data = await session_service.load_session(session_id, flow_id=flow_id_str)
            graph, artifacts = session_data if session_data else (None, None)
            if graph is None:
                raise ValueError(f"Session {session_id} not found")
        else:
            # Get the flow that matches the flow_id and belongs to the user
            # flow = session.query(Flow).filter(Flow.id == flow_id).filter(Flow.user_id == api_key_user.id).first()
            flow = session.exec(
                select(Flow).where(Flow.id == flow_id_str).where(Flow.user_id == api_key_user.id)
            ).first()
            if flow is None:
                raise ValueError(f"Flow {flow_id_str} not found")

            if flow.data is None:
                raise ValueError(f"Flow {flow_id_str} has no data")
            graph_data = flow.data
            graph_data = process_tweaks(graph_data, tweaks or {})
            graph = Graph.from_payload(graph_data, flow_id=flow_id_str)
        task_result, session_id = await run_graph_internal(
            graph=graph,
            flow_id=flow_id_str,
            session_id=session_id,
            inputs=inputs,
            outputs=outputs,
            stream=stream,
        )

        return RunResponse(outputs=task_result, session_id=session_id)
    except sa.exc.StatementError as exc:
        # StatementError('(builtins.ValueError) badly formed hexadecimal UUID string')
        if "badly formed hexadecimal UUID string" in str(exc):
            logger.error(f"Flow ID {flow_id_str} is not a valid UUID")
            # This means the Flow ID is not a valid UUID which means it can't find the flow
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        if f"Flow {flow_id_str} not found" in str(exc):
            logger.error(f"Flow {flow_id_str} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        elif f"Session {session_id} not found" in str(exc):
            logger.error(f"Session {session_id} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        else:
            logger.exception(exc)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post(
    "/predict/{flow_id}",
    response_model=ProcessResponse,
    dependencies=[Depends(api_key_security)],
)
@router.post(
    "/process/{flow_id}",
    response_model=ProcessResponse,
)
async def process(
    session: Annotated[Session, Depends(get_session)],
    flow_id: str,
    inputs: Optional[Union[List[dict], dict]] = None,
    tweaks: Optional[dict] = None,
    clear_cache: Annotated[bool, Body(embed=True)] = False,  # noqa: F821
    session_id: Annotated[Union[None, str], Body(embed=True)] = None,  # noqa: F821
    task_service: "TaskService" = Depends(get_task_service),
    api_key_user: User = Depends(api_key_security),
    sync: Annotated[bool, Body(embed=True)] = True,  # noqa: F821
    session_service: SessionService = Depends(get_session_service),
):
    """
    Endpoint to process an input with a given flow_id.
    """
    # Raise a depreciation warning
    logger.warning(
        "The /process endpoint is deprecated and will be removed in a future version. " "Please use /run instead."
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The /process endpoint is deprecated and will be removed in a future version. "
        "Please use /run instead.",
    )


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    task_service = get_task_service()
    task = task_service.get_task(task_id)
    result = None
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.ready():
        result = task.result
        # If result isinstance of Exception, can we get the traceback?
        if isinstance(result, Exception):
            logger.exception(task.traceback)

        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        elif hasattr(result, "result"):
            result = result.result

    if task.status == "FAILURE":
        result = str(task.result)
        logger.error(f"Task {task_id} failed: {task.traceback}")

    return TaskStatusResponse(status=task.status, result=result)


@router.post(
    "/upload/{flow_id}",
    response_model=UploadFileResponse,
    status_code=HTTPStatus.CREATED,
)
async def create_upload_file(
    file: UploadFile,
    flow_id: UUID,
):
    try:
        flow_id_str = str(flow_id)
        file_path = save_uploaded_file(file, folder_name=flow_id_str)

        return UploadFileResponse(
            flowId=flow_id_str,
            file_path=file_path,
        )
    except Exception as exc:
        logger.error(f"Error saving file: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# get endpoint to return version of langflow
@router.get("/version")
def get_version():
    return get_version_info()


@router.post("/custom_component", status_code=HTTPStatus.OK, response_model=CustomComponentResponse)
async def custom_component(
    raw_code: CustomComponentRequest,
    user: User = Depends(get_current_active_user),
):
    component = Component(code=raw_code.code)

    built_frontend_node, component_instance = build_custom_component_template(component, user_id=user.id)
    if raw_code.frontend_node is not None:
        built_frontend_node = component_instance.post_code_processing(built_frontend_node, raw_code.frontend_node)

    _type = get_instance_name(component_instance)
    return CustomComponentResponse(data=built_frontend_node, type=_type)


@router.post("/custom_component/update", status_code=HTTPStatus.OK)
async def custom_component_update(
    code_request: UpdateCustomComponentRequest,
    user: User = Depends(get_current_active_user),
):
    """
    Update a custom component with the provided code request.

    This endpoint generates the CustomComponentFrontendNode normally but then runs the `update_build_config` method
    on the latest version of the template. This ensures that every time it runs, it has the latest version of the template.

    Args:
        code_request (CustomComponentRequest): The code request containing the updated code for the custom component.
        user (User, optional): The user making the request. Defaults to the current active user.

    Returns:
        dict: The updated custom component node.

    """
    try:
        component = Component(code=code_request.code)

        component_node, cc_instance = build_custom_component_template(
            component,
            user_id=user.id,
        )
        if hasattr(cc_instance, "set_attributes"):
            template = code_request.get_template()
            params = {
                key: value_dict.get("value") for key, value_dict in template.items() if isinstance(value_dict, dict)
            }
            load_from_db_fields = [
                field_name
                for field_name, field_dict in template.items()
                if isinstance(field_dict, dict) and field_dict.get("load_from_db")
            ]
            params = update_params_with_load_from_db_fields(cc_instance, params, load_from_db_fields)
            cc_instance.set_attributes(params)
        updated_build_config = code_request.get_template()
        cc_instance.update_build_config(
            build_config=updated_build_config,
            field_value=code_request.field_value,
            field_name=code_request.field,
        )
        component_node["template"] = updated_build_config

        return component_node
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/config", response_model=ConfigResponse)
def get_config():
    try:
        from langflow.services.deps import get_settings_service

        settings_service: "SettingsService" = get_settings_service()  # type: ignore
        return settings_service.settings.model_dump()
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
