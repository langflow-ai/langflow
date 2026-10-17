"""Gpt Image task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class GPTImageRetrieveTaskComponent(AceTaskComponent):
    display_name = "GPT Image Retrieve Task by Ace Data Cloud"
    description = "Query the same GPT Image task through Ace Data Cloud without another paid generation."
    icon = "Image"
    documentation = "https://docs.langflow.org/acedatacloud-gpt-image"
    service_name = "gpt_image"
    inputs = task_inputs("gpt_image")
