"""Inspect a public agent endpoint before deciding whether to delegate work."""

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from lfx_bundles.agentguild.agentguild_common import public_endpoint, read_json


class AgentGuildPreflight(Component):
    """Return observed endpoint evidence, including failed and unavailable checks."""

    display_name = "Agent Guild Preflight"
    description = "Inspect a public agent endpoint before delegation. Free; no API key or wallet required."
    name = "AgentGuildPreflight"
    icon = "AgentGuild"
    documentation = "https://github.com/AgentTanuki/agent-guild"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="Public Endpoint URL",
            required=True,
            tool_mode=True,
            info="Public HTTP(S) endpoint to send to Agent Guild for probing. Do not include credentials.",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=30,
            advanced=True,
            info="Request timeout, from 1 to 60 seconds.",
        ),
    ]
    outputs = [Output(display_name="Preflight", name="data", method="inspect_endpoint")]

    async def inspect_endpoint(self) -> Data:
        """Fetch free preflight evidence without interpreting it as authorization."""
        endpoint = public_endpoint(self.url)
        result = await read_json("/preflight", timeout=self.timeout, params={"url": endpoint})
        if (
            not isinstance(result.get("verdict"), str)
            or not isinstance(result.get("failed"), list)
            or not isinstance(result.get("unknowns"), list)
        ):
            msg = "Agent Guild returned preflight data without verdict, failed checks, or unknowns."
            raise TypeError(msg)
        data = Data(data=result)
        self.status = data
        return data
