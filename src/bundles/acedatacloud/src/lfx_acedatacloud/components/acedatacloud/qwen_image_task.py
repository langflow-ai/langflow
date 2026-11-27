"""Qwen Image task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class QwenImageRetrieveTaskComponent(AceTaskComponent):
    display_name = "Qwen Image Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "qwen_image"
    inputs = task_inputs("qwen_image")
