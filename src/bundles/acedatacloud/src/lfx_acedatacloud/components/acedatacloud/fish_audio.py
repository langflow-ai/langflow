"""Fish Audio generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class FishAudioGenerateComponent(AceGenerationComponent):
    display_name = "Fish Audio Generate"
    description = "Run the Ace Data Cloud Fish Audio first-run API action."
    icon = "Bot"
    service_name = "fish_audio"
    inputs = generation_inputs("fish_audio")
