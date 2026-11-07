"""Happy Horse generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class HappyHorseGenerateComponent(AceGenerationComponent):
    display_name = "Happy Horse Generate by Ace Data Cloud"
    description = "Generate Happy Horse (HappyHorse) videos through Ace Data Cloud."
    icon = "Clapperboard"
    documentation = "https://docs.langflow.org/acedatacloud-happy-horse"
    service_name = "happy_horse"
    inputs = generation_inputs("happy_horse")
