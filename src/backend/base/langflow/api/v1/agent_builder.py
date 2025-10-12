"""Agent Builder API endpoint with streaming support."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from langflow.api.v1.schemas import AgentBuilderRequest, StreamData
from langflow.services.knowledge_base.service import get_knowledge_base_service

if TYPE_CHECKING:
    from langflow.services.knowledge_base.service import AgentMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-builder", tags=["Agent Builder"])


async def stream_agent_builder_events(request: AgentBuilderRequest) -> AsyncGenerator[str, None]:
    """Stream agent builder events using Server-Sent Events format.

    Args:
        request: Agent builder request with user prompt

    Yields:
        SSE formatted event strings
    """
    try:
        # Use Multi-Agent Orchestrator with Master Planning + Builder agents
        from langflow.custom.genesis.services.agent_builder.multi_agent_orchestrator import MultiAgentOrchestrator

        # Initialize orchestrator with conversation history from request
        orchestrator = MultiAgentOrchestrator(conversation_history=request.conversation_history)

        # Stream the complete agent building pipeline
        async for event in orchestrator.build_streaming(request.prompt):
            yield str(event)

    except Exception as e:
        logger.exception(f"Error in agent builder stream: {e}")
        yield str(
            StreamData(
                event="error",
                data={"error": str(e), "message": "An error occurred while building the agent workflow."},
            )
        )


@router.post("/stream")
async def build_agent_stream(request: AgentBuilderRequest) -> StreamingResponse:
    """Build an agent workflow with streaming progress updates.

    This endpoint streams the agent building process in real-time:
    1. Analyzes user request
    2. Searches knowledge base for relevant agents
    3. Generates workflow recommendation
    4. Returns complete workflow structure

    Args:
        request: Agent builder request with user prompt

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


@router.post("/analyze")
async def analyze_request(request: AgentBuilderRequest) -> dict:
    """Non-streaming endpoint to analyze request and return matching agents.

    This is a simple endpoint for testing without streaming.

    Args:
        request: Agent builder request

    Returns:
        Dictionary with matching agents

    Raises:
        HTTPException: If an error occurs
    """
    try:
        kb_service = get_knowledge_base_service()
        matching_agents = kb_service.search_agents(request.prompt, top_k=5)

        return {
            "prompt": request.prompt,
            "agents_found": len(matching_agents),
            "agents": [agent.to_dict() for agent in matching_agents],
        }
    except Exception as e:
        logger.exception("Error analyzing request")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/agents")
async def list_all_agents() -> dict:
    """List all agents in the knowledge base.

    Returns:
        Dictionary with all agents

    Raises:
        HTTPException: If an error occurs
    """
    try:
        kb_service = get_knowledge_base_service()
        agents = kb_service.get_all_agents()

        return {
            "total": len(agents),
            "agents": [agent.to_dict() for agent in agents],
        }
    except Exception as e:
        logger.exception("Error listing agents")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/read-yaml")
async def read_yaml_file(file_path: str) -> dict:
    """Read YAML file from knowledge base.

    Args:
        file_path: Path to the YAML file (relative to knowledge_base directory)

    Returns:
        Dictionary with YAML content

    Raises:
        HTTPException: If file not found or error occurs
    """
    try:
        kb_service = get_knowledge_base_service()
        kb_path = kb_service.knowledge_base_path

        # Security: Ensure the file is within knowledge_base directory
        from pathlib import Path

        full_path = (kb_path / file_path).resolve()

        # Check if path is within knowledge_base
        if not str(full_path).startswith(str(kb_path)):
            raise HTTPException(status_code=400, detail="Invalid file path")

        # Check if file exists
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="YAML file not found")

        # Read file content
        with open(full_path, encoding="utf-8") as f:
            yaml_content = f.read()

        return {
            "content": yaml_content,
            "file_path": str(file_path),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error reading YAML file: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
