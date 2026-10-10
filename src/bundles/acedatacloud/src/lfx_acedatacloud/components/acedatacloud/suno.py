"""Suno generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class SunoGenerateComponent(AceGenerationComponent):
    display_name = "Suno Generate"
    description = "Run the Ace Data Cloud Suno first-run API action."
    icon = "Bot"
    service_name = "suno"
    inputs = generation_inputs("suno")
