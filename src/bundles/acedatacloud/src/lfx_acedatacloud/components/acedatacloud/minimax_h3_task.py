"""Minimax H3 task reader."""

from lfx_acedatacloud.components.base import AceTaskComponent, task_inputs


class MiniMaxH3RetrieveTaskComponent(AceTaskComponent):
    display_name = "MiniMax H3 Retrieve Task"
    description = "Read a submitted task without starting another paid generation."
    icon = "Bot"
    service_name = "minimax_h3"
    inputs = task_inputs("minimax_h3")
