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
        # Step 1: Analyze request
        yield str(StreamData(event="thinking", data={"message": "Analyzing your request..."}))
        await asyncio.sleep(0.5)  # Simulate processing

        # Step 2: Search knowledge base
        yield str(StreamData(event="thinking", data={"message": "Searching knowledge base for relevant agents..."}))
        await asyncio.sleep(0.3)

        kb_service = get_knowledge_base_service()
        matching_agents: list[AgentMetadata] = kb_service.search_agents(request.prompt, top_k=5)

        if not matching_agents:
            yield str(
                StreamData(
                    event="error",
                    data={"error": "No matching agents found in knowledge base. Please try a different query."},
                )
            )
            return

        yield str(
            StreamData(
                event="thinking",
                data={"message": f"Found {len(matching_agents)} relevant agents in knowledge base."},
            )
        )
        await asyncio.sleep(0.2)

        # Step 3: Stream each found agent
        for i, agent in enumerate(matching_agents, 1):
            yield str(
                StreamData(
                    event="thinking",
                    data={"message": f"Analyzing agent {i}/{len(matching_agents)}: {agent.name}"},
                )
            )
            await asyncio.sleep(0.2)

            yield str(
                StreamData(
                    event="agent_found",
                    data={
                        "agent": agent.to_dict(),
                        "index": i,
                        "total": len(matching_agents),
                    },
                )
            )
            await asyncio.sleep(0.1)

        # Step 4: Prepare agent data for LLM (POC - without actual LLM call)
        yield str(StreamData(event="thinking", data={"message": "Generating workflow recommendation..."}))
        await asyncio.sleep(0.5)

        # POC: Simple workflow generation without LLM
        # In next phase, we'll integrate actual LLM here
        workflow = {
            "name": "Generated Workflow",
            "description": f"Workflow based on: {request.prompt}",
            "components": [
                {"id": "input-1", "type": "ChatInput", "name": "User Input"},
            ],
            "agents_used": [agent.to_dict() for agent in matching_agents[:3]],  # Use top 3
        }

        # Add agents as components
        for i, agent in enumerate(matching_agents[:3]):
            workflow["components"].append(
                {
                    "id": f"agent-{i+1}",
                    "type": "Agent",
                    "name": agent.name,
                    "config": {
                        "agent_id": agent.id,
                        "description": agent.description,
                    },
                }
            )

        # Add output
        workflow["components"].append({"id": "output-1", "type": "ChatOutput", "name": "Result"})

        yield str(
            StreamData(
                event="thinking",
                data={"message": "Workflow generated successfully! Ready to build."},
            )
        )
        await asyncio.sleep(0.3)

        # Step 5: Send complete response
        yield str(
            StreamData(
                event="complete",
                data={
                    "workflow": workflow,
                    "agents_count": len(matching_agents),
                    "reasoning": f"Based on your request '{request.prompt}', I've identified {len(matching_agents)} "
                    f"relevant agents and created a workflow using the top 3: "
                    f"{', '.join(a.name for a in matching_agents[:3])}",
                },
            )
        )

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
