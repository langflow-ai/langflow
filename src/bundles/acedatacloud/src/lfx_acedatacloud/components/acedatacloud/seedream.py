"""Seedream generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class SeedreamGenerateComponent(AceGenerationComponent):
    display_name = "Seedream Generate"
    description = "Run the Ace Data Cloud Seedream first-run API action."
    icon = "Bot"
    service_name = "seedream"
    inputs = generation_inputs("seedream")
