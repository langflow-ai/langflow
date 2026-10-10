"""Seedance generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class SeedanceGenerateComponent(AceGenerationComponent):
    display_name = "Seedance Generate"
    description = "Run the Ace Data Cloud Seedance first-run API action."
    icon = "Bot"
    service_name = "seedance"
    inputs = generation_inputs("seedance")
