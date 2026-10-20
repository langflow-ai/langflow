"""Seedream task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class SeedreamRetrieveTaskComponent(AceTaskComponent):
    display_name = "Seedream Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "seedream"
    inputs = task_inputs("seedream")
