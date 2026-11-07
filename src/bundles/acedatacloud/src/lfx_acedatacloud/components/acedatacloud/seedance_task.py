"""Seedance task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class SeedanceRetrieveTaskComponent(AceTaskComponent):
    display_name = "Seedance Retrieve Task by Ace Data Cloud"
    description = "Query the same Seedance task through Ace Data Cloud without another paid generation."
    icon = "Clapperboard"
    documentation = "https://docs.langflow.org/acedatacloud-seedance"
    service_name = "seedance"
    inputs = task_inputs("seedance")
