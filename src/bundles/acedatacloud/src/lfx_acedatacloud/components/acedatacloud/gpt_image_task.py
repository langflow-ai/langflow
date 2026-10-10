"""Gpt Image task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class GPTImageRetrieveTaskComponent(AceTaskComponent):
    display_name = "GPT Image Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "gpt_image"
    inputs = task_inputs("gpt_image")
