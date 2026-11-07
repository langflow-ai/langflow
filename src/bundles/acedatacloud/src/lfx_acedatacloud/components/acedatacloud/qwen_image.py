"""Qwen Image generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class QwenImageGenerateComponent(AceGenerationComponent):
    display_name = "Qwen Image Generate"
    description = "Run the Ace Data Cloud Qwen Image first-run API action."
    icon = "Bot"
    service_name = "qwen_image"
    inputs = generation_inputs("qwen_image")
