"""Wan generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class WanGenerateComponent(AceGenerationComponent):
    display_name = "Wan Generate"
    description = "Run the Ace Data Cloud Wan first-run API action."
    icon = "Bot"
    service_name = "wan"
    inputs = generation_inputs("wan")
