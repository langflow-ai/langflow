"""Nano Banana generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class NanoBananaGenerateComponent(AceGenerationComponent):
    display_name = "Nano Banana Generate"
    description = "Run the Ace Data Cloud Nano Banana first-run API action."
    icon = "Bot"
    service_name = "nano_banana"
    inputs = generation_inputs("nano_banana")
