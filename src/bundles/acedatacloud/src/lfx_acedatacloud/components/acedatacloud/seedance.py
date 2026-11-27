"""Seedance generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class SeedanceGenerateComponent(AceGenerationComponent):
    display_name = "Seedance Generate by Ace Data Cloud"
    description = "Generate Seedance videos through Ace Data Cloud."
    icon = "Clapperboard"
    documentation = "https://docs.langflow.org/acedatacloud-seedance"
    service_name = "seedance"
    inputs = generation_inputs("seedance")
