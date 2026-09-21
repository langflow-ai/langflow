"""Discover current trust-operation prices without making a purchase."""

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, Output
from lfx.schema.data import Data

from lfx_bundles.agentguild.agentguild_common import read_json


class AgentGuildPaidOperations(Component):
    """Return the free paid-operation catalog from Agent Guild's public manifest."""

    display_name = "Agent Guild Paid Operations"
    description = "Read current trust-operation prices, entrypoints, and free alternatives. This call is free."
    name = "AgentGuildPaidOperations"
    icon = "AgentGuild"
    documentation = "https://github.com/AgentTanuki/agent-guild"

    inputs = [
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=30,
            advanced=True,
            tool_mode=True,
            info="Request timeout, from 1 to 60 seconds. Reading prices does not make a purchase.",
        ),
    ]
    outputs = [Output(display_name="Paid Operations", name="data", method="read_prices")]

    async def read_prices(self) -> Data:
        """Read the catalog while keeping all callable operations outside this component."""
        manifest = await read_json("/.well-known/agent-guild.json", timeout=self.timeout)
        catalog = manifest.get("paid_operations")
        if not isinstance(catalog, dict) or not isinstance(catalog.get("operations"), list):
            msg = "Agent Guild returned a manifest without a paid-operation catalog."
            raise TypeError(msg)
        data = Data(data=catalog)
        self.status = data
        return data
