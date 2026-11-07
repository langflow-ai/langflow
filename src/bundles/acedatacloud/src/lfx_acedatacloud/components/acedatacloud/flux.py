"""Flux generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class FluxGenerateComponent(AceGenerationComponent):
    display_name = "Flux Generate"
    description = "Run the Ace Data Cloud Flux first-run API action."
    icon = "Bot"
    service_name = "flux"
    inputs = generation_inputs("flux")
