"""Nano Banana generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class NanoBananaGenerateComponent(AceGenerationComponent):
    display_name = "Nano Banana Generate by Ace Data Cloud"
    description = "Generate Nano Banana (NanoBanana) images through Ace Data Cloud."
    icon = "Image"
    documentation = "https://docs.langflow.org/acedatacloud-nano-banana"
    service_name = "nano_banana"
    inputs = generation_inputs("nano_banana")
