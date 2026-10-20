"""Suno generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class SunoGenerateComponent(AceGenerationComponent):
    display_name = "Suno Generate by Ace Data Cloud"
    description = "Generate Suno music and audio through Ace Data Cloud."
    icon = "Music"
    documentation = "https://docs.langflow.org/acedatacloud-suno"
    service_name = "suno"
    inputs = generation_inputs("suno")
