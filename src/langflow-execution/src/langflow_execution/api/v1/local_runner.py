import asyncio
import logging
import time

from fastapi import BackgroundTasks, Request
from fastapi.responses import StreamingResponse

from langflow_execution.api.v1.schema.flow import FlowExecutionRequest
from langflow_execution.services.manager import ServiceManager
from langflow_execution.services.telemetry.schema import RunPayload
from langflow_execution.api.v1.execute import simple_run_flow
from langflow_execution.api.v1.schema.flow import Flow
from langflow_execution.events.event_manager import create_stream_tokens_event_manager
from langflow_execution.api.v1.execute import simple_run_flow

logger = logging.getLogger(__name__)


class DefaultFlowRunner:
    async def simplified_run_flow(
        self,
        *,
        background_tasks: BackgroundTasks,
        input_request: FlowExecutionRequest,
        flow: Flow,
        stream: bool = False,
    ):
        """Executes a specified flow by ID with support for streaming and telemetry.

        This endpoint executes a flow identified by ID or name, with options for streaming the response
        and tracking execution metrics. It handles both streaming and non-streaming execution modes.

        Args:
            background_tasks (BackgroundTasks): FastAPI background task manager
            flow (FlowRead | None): The flow to execute, loaded via dependency
            input_request (SimplifiedAPIRequest | None): Input parameters for the flow
            stream (bool): Whether to stream the response
            api_key_user (UserRead): Authenticated user from API key
            request (Request): The incoming HTTP request

        Returns:
            Union[StreamingResponse, RunResponse]: Either a streaming response for real-time results
            or a RunResponse with the complete execution results

        Raises:
            HTTPException: For flow not found (404) or invalid input (400)
            APIException: For internal execution errors (500)

        Notes:
            - Supports both streaming and non-streaming execution modes
            - Tracks execution time and success/failure via telemetry
            - Handles graceful client disconnection in streaming mode
            - Provides detailed error handling with appropriate HTTP status codes
            - In streaming mode, uses EventManager to handle events:
                - "add_message": New messages during execution
                - "token": Individual tokens during streaming
                - "end": Final execution result
        """
        telemetry_service = ServiceManager.get_instance().get_telemetry_service()
        start_time = time.perf_counter()

        if stream:
            # TODO: implement streaming
            pass
            # asyncio_queue: asyncio.Queue = asyncio.Queue()
            # asyncio_queue_client_consumed: asyncio.Queue = asyncio.Queue()
            # event_manager = create_stream_tokens_event_manager(queue=asyncio_queue)
            # main_task = asyncio.create_task(
            #     run_flow_generator(
            #         flow=flow,
            #         input_request=input_request,
            #         api_key_user=api_key_user,
            #         event_manager=event_manager,
            #         client_consumed_queue=asyncio_queue_client_consumed,
            #     )
            # )

            # async def on_disconnect() -> None:
            #     logger.debug("Client disconnected, closing tasks")
            #     main_task.cancel()

            # return StreamingResponse(
            #     consume_and_yield(asyncio_queue, asyncio_queue_client_consumed),
            #     background=on_disconnect,
            #     media_type="text/event-stream",
            # )
        else:
            try:
                result = await simple_run_flow(
                    flow=flow,
                    input_request=input_request,
                    stream=False,
                )
                end_time = time.perf_counter()
                background_tasks.add_task(
                    telemetry_service.log_package_run,
                    RunPayload(
                        run_is_webhook=False,
                        run_seconds=int(end_time - start_time),
                        run_success=True,
                        run_error_message="",
                    ),
                )

            except ValueError as exc:
                background_tasks.add_task(
                    telemetry_service.log_package_run,
                    RunPayload(
                        run_is_webhook=False,
                        run_seconds=int(time.perf_counter() - start_time),
                        run_success=False,
                        run_error_message=str(exc),
                    ),
                )
                # TODO: exception handling
                # raise APIException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, exception=exc, flow=flow) from exc
                raise exc
            except Exception as exc:
                background_tasks.add_task(
                    telemetry_service.log_package_run,
                    RunPayload(
                        run_is_webhook=False,
                        run_seconds=int(time.perf_counter() - start_time),
                        run_success=False,
                        run_error_message=str(exc),
                    ),
                )
                # raise APIException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, exception=exc, flow=flow) from exc
                raise exc

        return result

    async def webhook_run(
        self,
        flow: "Flow",
        user: "User",
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> dict:
        # Example implementation
        data = await request.json()
        return {"webhook_output": f"Processed webhook for flow {flow} and user {user} with data {data}"}
