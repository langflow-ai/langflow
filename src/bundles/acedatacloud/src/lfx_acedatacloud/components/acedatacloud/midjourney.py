"""Midjourney generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class MidjourneyGenerateComponent(AceGenerationComponent):
    display_name = "Midjourney Generate"
    description = "Run the Ace Data Cloud Midjourney first-run API action."
    icon = "Bot"
    service_name = "midjourney"
    inputs = generation_inputs("midjourney")
