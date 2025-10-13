"""
Simplified Agent Builder Orchestrator - Calls unified flow via HTTP API
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx

from langflow.custom.genesis.core.config import settings

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """Simplified orchestrator that calls a single unified agent builder flow via HTTP"""

    def __init__(self, session_id: str | None = None, **kwargs):
        """Initialize orchestrator with unified flow ID and optional session ID

        Args:
            session_id: Optional session ID for conversation continuity.
                       If not provided, a new UUID will be generated.
        """
        self.logger = logging.getLogger(__name__)

        # Load flow ID from BuilderAgent.json (single source of truth)
        self.flow_id = self._load_builder_agent_flow_id()

        # Langflow API base URL from config
        self.base_url = settings.LANGFLOW_API_URL

        # Use provided session ID or generate new one for conversation continuity
        self.session_id = session_id or str(uuid.uuid4())

    def _load_builder_agent_flow_id(self) -> str:
        """Load the Builder Agent flow ID from BuilderAgent.json file.

        Returns:
            Flow ID from the JSON file

        Raises:
            FileNotFoundError: If BuilderAgent.json is not found
            ValueError: If the JSON file is invalid or missing the 'id' field
        """
        try:
            # Path to BuilderAgent.json relative to this file
            builder_agent_path = (
                Path(__file__).parent.parent.parent.parent.parent
                / "initial_setup"
                / "builder_agent"
                / "BuilderAgent.json"
            )

            with open(builder_agent_path, encoding="utf-8") as f:
                flow_data = json.load(f)

            flow_id = flow_data.get("id")
            if not flow_id:
                msg = "BuilderAgent.json is missing the 'id' field"
                raise ValueError(msg)

            self.logger.debug(f"Loaded Builder Agent flow ID: {flow_id}")
            return flow_id

        except FileNotFoundError as e:
            self.logger.error(f"BuilderAgent.json not found at {builder_agent_path}")
            raise FileNotFoundError(
                f"BuilderAgent.json not found. Expected at: {builder_agent_path}"
            ) from e
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in BuilderAgent.json: {e}")
            raise ValueError(f"BuilderAgent.json contains invalid JSON: {e}") from e

    async def build_streaming(self, user_input: str) -> AsyncGenerator[str, None]:
        """
        Call the unified agent builder flow via HTTP streaming API

        Passes through Langflow's native events as-is in SSE format.

        Args:
            user_input: User's message/prompt

        Yields:
            SSE formatted event strings with Langflow's native event types
        """
        try:
            self.logger.info(f"Calling unified flow {self.flow_id} with input: {user_input[:100]}...")

            # Prepare the API endpoint with streaming enabled
            url = f"{self.base_url}/api/v1/run/{self.flow_id}"

            # Prepare payload matching Langflow's run API format
            # Use persistent session ID for conversation continuity
            payload = {
                "input_value": user_input,
                "input_type": "chat",
                "output_type": "chat",
                "session_id": self.session_id
            }

            self.logger.info(f"Making request to: {url}")
            self.logger.debug(f"Payload: {payload}")

            # Make streaming HTTP request
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    params={"stream": "true"}  # Enable streaming
                ) as response:
                    response.raise_for_status()

                    # Stream the response line by line
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            # Parse Langflow's JSON event
                            event_data = json.loads(line)

                            # Extract event type and data
                            event_type = event_data.get("event")
                            data = event_data.get("data", {})

                            self.logger.debug(f"Received event type: {event_type}")
                            self.logger.debug(f"Event data: {json.dumps(data, indent=2)[:500]}")

                            # Skip user messages (frontend already has them)
                            if data.get("sender") == "User":
                                continue

                            # Pass through Langflow's event as-is in SSE format
                            sse_event = self._format_sse(event_type, data)
                            yield sse_event

                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Failed to parse JSON line: {line[:100]}... Error: {e}")
                            continue
                        except Exception as e:
                            self.logger.error(f"Error processing line: {e}")
                            continue

            self.logger.info("Flow streaming completed successfully")

        except httpx.HTTPStatusError as e:
            self.logger.exception(f"HTTP error calling flow: {e}")
            yield self._format_sse("error", {
                "error": f"HTTP {e.response.status_code}",
                "message": "Failed to call agent flow"
            })
        except Exception as e:
            self.logger.exception(f"Error in orchestrator: {e}")
            yield self._format_sse("error", {
                "error": str(e),
                "message": "An error occurred while processing your request"
            })

    def _format_sse(self, event_type: str, data: dict) -> str:
        """
        Format data as Server-Sent Event

        Args:
            event_type: Langflow's native event type (add_message, token, end, error, etc.)
            data: Data payload from Langflow

        Returns:
            Formatted SSE string
        """
        # Convert data to JSON
        data_json = json.dumps(data)
        # Format as SSE with double newline at end
        return f"event: {event_type}\ndata: {data_json}\n\n"
