"""Suno task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class SunoRetrieveTaskComponent(AceTaskComponent):
    display_name = "Suno Retrieve Task by Ace Data Cloud"
    description = "Query the same Suno task through Ace Data Cloud without another paid generation."
    icon = "Music"
    documentation = "https://docs.langflow.org/acedatacloud-suno"
    service_name = "suno"
    inputs = task_inputs("suno")
