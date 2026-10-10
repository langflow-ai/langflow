"""Gpt Image generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class GPTImageGenerateComponent(AceGenerationComponent):
    display_name = "GPT Image Generate"
    description = "Run the Ace Data Cloud GPT Image first-run API action."
    icon = "Bot"
    service_name = "gpt_image"
    inputs = generation_inputs("gpt_image")
