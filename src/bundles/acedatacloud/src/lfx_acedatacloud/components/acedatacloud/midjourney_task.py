"""Midjourney task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class MidjourneyRetrieveTaskComponent(AceTaskComponent):
    display_name = "Midjourney Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "midjourney"
    inputs = task_inputs("midjourney")
