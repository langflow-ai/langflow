"""A2A client component: send a message to a remote A2A agent and return its reply.

Langflow can also be an A2A *server* (see the langflow A2A routes); this is the other
direction, letting a flow call out to any spec-compliant A2A agent via the a2a-sdk client.
"""

from __future__ import annotations

import uuid

import httpx

from lfx.custom import Component
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.schema.message import Message


async def call_a2a_agent(
    agent_url: str,
    message: str,
    *,
    httpx_client: httpx.AsyncClient,
    accepted_output_modes: list[str] | None = None,
) -> str:
    """Send ``message`` to the A2A agent at ``agent_url`` and return its reply text.

    Resolves the agent card from ``<agent_url>/.well-known/agent-card.json``, sends one
    non-streaming ``message/send``, and joins the text parts of the returned artifacts
    (falling back to the task's status message). The same ``httpx_client`` fetches the card
    and posts the message, so any auth header set on it (e.g. ``x-api-key``) reaches an
    auth-gated agent. Factored out from the component so a test can drive it with an
    in-process transport.
    """
    from a2a.client.client import ClientConfig
    from a2a.client.client_factory import create_client
    from a2a.helpers.proto_helpers import get_text_parts, new_text_part
    from a2a.types import a2a_pb2 as pb

    client = await create_client(
        agent_url,
        client_config=ClientConfig(
            streaming=False,
            httpx_client=httpx_client,
            accepted_output_modes=accepted_output_modes or ["application/json"],
        ),
    )
    request = pb.SendMessageRequest(
        message=pb.Message(
            message_id=uuid.uuid4().hex,
            role=pb.Role.ROLE_USER,
            parts=[new_text_part(message)],
        )
    )
    texts: list[str] = []
    async for response in client.send_message(request):
        if response.HasField("task"):
            for artifact in response.task.artifacts:
                texts.extend(get_text_parts(artifact.parts))
            if not texts and response.task.status.HasField("message"):
                texts.extend(get_text_parts(response.task.status.message.parts))
        elif response.HasField("message"):
            texts.extend(get_text_parts(response.message.parts))
    return "\n".join(text for text in texts if text)


class A2AAgentComponent(Component):
    display_name = "A2A Agent"
    description = "Send a message to a remote A2A (Agent-to-Agent) agent and return its reply."
    documentation: str = "https://a2a-protocol.org/"
    icon = "bot"
    name = "A2AAgent"

    inputs = [
        MessageTextInput(
            name="agent_url",
            display_name="Agent URL",
            info="Base URL of the remote A2A agent. Its card is fetched from <url>/.well-known/agent-card.json.",
            required=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Message",
            info="The message to send to the agent.",
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Optional API key sent as x-api-key, for agents that require it.",
            advanced=True,
            required=False,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (s)",
            info="Maximum seconds to wait for the agent's reply.",
            value=60,
            advanced=True,
        ),
    ]
    outputs = [Output(display_name="Response", name="response", method="send_to_agent")]

    async def send_to_agent(self) -> Message:
        headers = {"x-api-key": self.api_key} if self.api_key else None
        async with httpx.AsyncClient(timeout=float(self.timeout), headers=headers) as http_client:
            answer = await call_a2a_agent(self.agent_url, self.input_value, httpx_client=http_client)
        message = Message(text=answer)
        self.status = message
        return message
