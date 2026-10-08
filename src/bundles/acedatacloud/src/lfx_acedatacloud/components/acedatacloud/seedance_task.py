"""Seedance task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class SeedanceRetrieveTaskComponent(AceTaskComponent):
    display_name = "Seedance Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "seedance"
    inputs = task_inputs("seedance")
