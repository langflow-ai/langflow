"""Veo generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class VeoGenerateComponent(AceGenerationComponent):
    display_name = "Veo Generate"
    description = "Run the Ace Data Cloud Veo first-run API action."
    icon = "Bot"
    service_name = "veo"
    inputs = generation_inputs("veo")
