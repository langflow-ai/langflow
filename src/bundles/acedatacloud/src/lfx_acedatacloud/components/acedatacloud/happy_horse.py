"""Happy Horse generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class HappyHorseGenerateComponent(AceGenerationComponent):
    display_name = "Happy Horse Generate"
    description = "Run the Ace Data Cloud Happy Horse first-run API action."
    icon = "Bot"
    service_name = "happy_horse"
    inputs = generation_inputs("happy_horse")
