"""Agent Builder API endpoint with streaming support."""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from langflow.api.v1.schemas import AgentBuilderRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-builder", tags=["Agent Builder"])


async def stream_agent_builder_events(request: AgentBuilderRequest) -> AsyncGenerator[str, None]:
    """Stream agent builder events using Server-Sent Events format.

    Args:
        request: Agent builder request with user prompt and optional session_id

    Yields:
        SSE formatted event strings
    """
    try:
        # Use the unified multi-orchestrator flow
        from langflow.services.genesis.orchestrator import MultiAgentOrchestrator

        # Initialize orchestrator with session_id from request
        orchestrator = MultiAgentOrchestrator(session_id=request.session_id)

        # Stream the complete agent building pipeline
        async for event in orchestrator.build_streaming(request.prompt):
            yield str(event)

    except Exception as e:
        logger.exception(f"Error in agent builder stream: {e}")
        yield f"event: error\ndata: {{\"error\": \"{str(e)}\", \"message\": \"An error occurred while building the agent workflow.\"}}\n\n"


@router.post("/stream")
async def build_agent_stream(request: AgentBuilderRequest) -> StreamingResponse:
    """Build an agent workflow with streaming progress updates.

    The unified flow handles everything internally:
    - User interaction and conversation
    - Knowledge base access
    - Planning and architecture design
    - YAML generation

    Args:
        request: Agent builder request with user prompt and optional session_id

    Returns:
        StreamingResponse with Server-Sent Events

    Raises:
        HTTPException: If an error occurs during processing
    """
    try:
        return StreamingResponse(
            stream_agent_builder_events(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    except Exception as e:
        logger.exception("Error creating agent builder stream")
        raise HTTPException(status_code=500, detail=str(e)) from e
