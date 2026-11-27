"""Kling generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class KlingGenerateComponent(AceGenerationComponent):
    display_name = "Kling Generate"
    description = "Run the Ace Data Cloud Kling first-run API action."
    icon = "Bot"
    service_name = "kling"
    inputs = generation_inputs("kling")
