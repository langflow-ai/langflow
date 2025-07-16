import asyncio
import time
import uuid
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger

from langflow.api.utils import parse_value
from langflow.api.v1.schemas import SimplifiedAPIRequest
from langflow.events.event_manager import create_stream_tokens_event_manager
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.schema.openai_responses_schemas import (
    OpenAIErrorResponse,
    OpenAIResponsesRequest,
    OpenAIResponsesResponse,
    OpenAIResponsesStreamChunk,
    create_openai_error,
)
from langflow.services.auth.utils import api_key_security
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_telemetry_service
from langflow.services.telemetry.schema import RunPayload

from .endpoints import consume_and_yield, run_flow_generator, simple_run_flow

router = APIRouter(tags=["OpenAI Responses API"])


def has_chat_input(flow_data: dict) -> bool:
    """Check if the flow has a chat input component."""
    if not flow_data or "nodes" not in flow_data:
        return False
    
    for node in flow_data["nodes"]:
        if node.get("data", {}).get("type") in ["ChatInput", "Chat Input"]:
            return True
    return False


async def run_flow_for_openai_responses(
    flow: FlowRead,
    request: OpenAIResponsesRequest,
    api_key_user: UserRead,
    stream: bool = False,
) -> OpenAIResponsesResponse | StreamingResponse:
    """Run a flow for OpenAI Responses API compatibility."""
    # Check if flow has chat input
    if not has_chat_input(flow.data):
        raise ValueError("Flow must have a ChatInput component to be compatible with OpenAI Responses API")
    
    # Use previous_response_id as session_id for conversation continuity
    # If no previous_response_id, create a new session_id
    session_id = request.previous_response_id or str(uuid.uuid4())
    
    # Convert OpenAI request to SimplifiedAPIRequest
    simplified_request = SimplifiedAPIRequest(
        input_value=request.input,
        input_type="chat",  # Use chat input type for better compatibility
        output_type="chat",  # Use chat output type for better compatibility
        tweaks={},
        session_id=session_id,
    )

    # Use session_id as response_id for OpenAI compatibility
    response_id = session_id
    created_timestamp = int(time.time())

    if stream:
        # Handle streaming response
        asyncio_queue: asyncio.Queue = asyncio.Queue()
        asyncio_queue_client_consumed: asyncio.Queue = asyncio.Queue()
        event_manager = create_stream_tokens_event_manager(queue=asyncio_queue)

        async def openai_stream_generator() -> AsyncGenerator[str, None]:
            """Convert Langflow events to OpenAI Responses API streaming format."""
            main_task = asyncio.create_task(
                run_flow_generator(
                    flow=flow,
                    input_request=simplified_request,
                    api_key_user=api_key_user,
                    event_manager=event_manager,
                    client_consumed_queue=asyncio_queue_client_consumed,
                )
            )

            try:
                # Send initial chunk to establish connection
                initial_chunk = OpenAIResponsesStreamChunk(
                    id=response_id,
                    created=created_timestamp,
                    model=request.model,
                    delta={"content": ""},
                )
                yield f"data: {initial_chunk.model_dump_json()}\n\n"

                tool_call_counter = 0
                processed_tools = set()  # Track processed tool calls to avoid duplicates
                
                async for event_data in consume_and_yield(asyncio_queue, asyncio_queue_client_consumed):
                    if event_data is None:
                        break

                    content = ""
                    
                    # Parse byte string events as JSON
                    if isinstance(event_data, bytes):
                        try:
                            import json
                            event_str = event_data.decode('utf-8')
                            parsed_event = json.loads(event_str)
                            
                            if isinstance(parsed_event, dict):
                                event_type = parsed_event.get("event")
                                data = parsed_event.get("data", {})
                                
                                # Handle add_message events
                                if event_type == "add_message":
                                    sender_name = data.get("sender_name", "")
                                    text = data.get("text", "")
                                    sender = data.get("sender", "")
                                    content_blocks = data.get("content_blocks", [])
                                    
                                    # Look for Agent Steps in content_blocks
                                    for block in content_blocks:
                                        if block.get("title") == "Agent Steps":
                                            contents = block.get("contents", [])
                                            for step in contents:
                                                # Look for tool_use type items
                                                if step.get("type") == "tool_use":
                                                    tool_name = step.get("name", "")
                                                    tool_input = step.get("tool_input", {})
                                                    tool_output = step.get("output")
                                                    
                                                    # Only emit tool calls with explicit tool names and meaningful arguments
                                                    if tool_name and tool_input and len(tool_input) > 0:
                                                        # Create unique identifier for this tool call
                                                        tool_signature = f"{tool_name}:{hash(str(sorted(tool_input.items())))}"
                                                        
                                                        # Skip if we've already processed this tool call
                                                        if tool_signature in processed_tools:
                                                            continue
                                                            
                                                        processed_tools.add(tool_signature)
                                                        tool_call_counter += 1
                                                        call_id = f"call_{tool_call_counter}"
                                                        tool_id = f"tc_{tool_call_counter}"
                                                        
                                                        # Send tool call added event
                                                        tool_call_event = {
                                                            "type": "response.output_item.added",
                                                            "item": {
                                                                "id": tool_id,
                                                                "type": "tool_call", 
                                                                "name": tool_name,
                                                                "arguments": tool_input,
                                                                "call_id": call_id
                                                            }
                                                        }
                                                        yield f"event: response.output_item.added\ndata: {json.dumps(tool_call_event)}\n\n"
                                                        
                                                        # If there's output, send completion event
                                                        if tool_output is not None:
                                                            tool_done_event = {
                                                                "type": "response.output_item.done",
                                                                "item": {
                                                                    "id": tool_id,
                                                                    "type": "tool_call",
                                                                    "status": "completed",
                                                                    "content": [{"type": "text", "text": str(tool_output)}],
                                                                    "call_id": call_id
                                                                }
                                                            }
                                                            yield f"event: response.output_item.done\ndata: {json.dumps(tool_done_event)}\n\n"
                                    
                                    # Extract text content for streaming (only AI responses)
                                    if sender in ["Machine", "AI", "Agent"] and text != request.input and sender_name == "Agent":
                                        content = text
                                    
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            continue
                    
                    # Only send chunks with actual content
                    if content:
                        chunk = OpenAIResponsesStreamChunk(
                            id=response_id,
                            created=created_timestamp,
                            model=request.model,
                            delta={"content": content},
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"

                # Send final completion chunk
                final_chunk = OpenAIResponsesStreamChunk(
                    id=response_id,
                    created=created_timestamp,
                    model=request.model,
                    delta={},
                    status="completed",
                )
                yield f"data: {final_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"Error in stream generator: {e}")
                error_response = create_openai_error(
                    message=str(e),
                    type_="processing_error",
                )
                yield f"data: {error_response}\n\n"
            finally:
                if not main_task.done():
                    main_task.cancel()

        return StreamingResponse(
            openai_stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )

    else:
        # Handle non-streaming response
        result = await simple_run_flow(
            flow=flow,
            input_request=simplified_request,
            stream=False,
            api_key_user=api_key_user,
        )

        # Extract output text from result following MCP pattern
        output_text = ""
        if result.outputs:
            for run_output in result.outputs:
                if run_output and run_output.outputs:
                    for component_output in run_output.outputs:
                        if component_output:
                            # Handle messages (final chat outputs)
                            if hasattr(component_output, 'messages') and component_output.messages:
                                for msg in component_output.messages:
                                    if hasattr(msg, 'message'):
                                        output_text = msg.message
                                        break
                            # Handle results
                            if not output_text and hasattr(component_output, 'results') and component_output.results:
                                for value in component_output.results.values():
                                    if hasattr(value, 'get_text'):
                                        output_text = value.get_text()
                                        break
                                    elif isinstance(value, str):
                                        output_text = value
                                        break
                        if output_text:
                            break
                if output_text:
                    break

        # Create output in the correct format
        output_message = {
            "type": "message",
            "id": f"msg_{response_id}",
            "status": "completed",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": output_text,
                    "annotations": []
                }
            ]
        }

        return OpenAIResponsesResponse(
            id=response_id,
            created_at=created_timestamp,
            model=request.model,
            output=[output_message],
            previous_response_id=request.previous_response_id,
        )


@router.post("/responses", response_model=None)
async def create_response(
    request: OpenAIResponsesRequest,
    background_tasks: BackgroundTasks,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
) -> OpenAIResponsesResponse | StreamingResponse | OpenAIErrorResponse:
    """Create a response using OpenAI Responses API format.
    
    This endpoint accepts a flow_id in the model parameter and processes 
    the input through the specified Langflow flow.
    
    Args:
        request: OpenAI Responses API request with model (flow_id) and input
        background_tasks: FastAPI background task manager
        api_key_user: Authenticated user from API key
        
    Returns:
        OpenAI-compatible response or streaming response
        
    Raises:
        HTTPException: For validation errors or flow execution issues
    """
    telemetry_service = get_telemetry_service()
    start_time = time.perf_counter()

    # Validate tools parameter - error out if tools are provided
    if request.tools is not None:
        error_response = create_openai_error(
            message="Tools are not supported yet",
            type_="invalid_request_error",
            code="tools_not_supported",
        )
        return OpenAIErrorResponse(error=error_response["error"])

    # Get flow using the model field (which contains flow_id)
    try:
        flow = await get_flow_by_id_or_endpoint_name(request.model, str(api_key_user.id))
    except HTTPException:
        flow = None
    
    if flow is None:
        error_response = create_openai_error(
            message=f"Flow with id '{request.model}' not found",
            type_="invalid_request_error",
            code="flow_not_found",
        )
        return OpenAIErrorResponse(error=error_response["error"])

    try:
        # Process the request
        result = await run_flow_for_openai_responses(
            flow=flow,
            request=request,
            api_key_user=api_key_user,
            stream=request.stream,
        )

        # Log telemetry for successful completion
        if not request.stream:  # Only log for non-streaming responses
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

        return result

    except Exception as exc:
        logger.error(f"Error processing OpenAI Responses request: {exc}")

        # Log telemetry for failed completion
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                run_is_webhook=False,
                run_seconds=int(time.perf_counter() - start_time),
                run_success=False,
                run_error_message=str(exc),
            ),
        )

        # Return OpenAI-compatible error
        error_response = create_openai_error(
            message=str(exc),
            type_="processing_error",
        )
        return OpenAIErrorResponse(error=error_response["error"])