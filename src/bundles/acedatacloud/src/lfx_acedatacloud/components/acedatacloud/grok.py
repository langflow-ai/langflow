"""Grok generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class GrokVideoGenerateComponent(AceGenerationComponent):
    display_name = "Grok Video Generate"
    description = "Run the Ace Data Cloud Grok Video first-run API action."
    icon = "Bot"
    service_name = "grok"
    inputs = generation_inputs("grok")
