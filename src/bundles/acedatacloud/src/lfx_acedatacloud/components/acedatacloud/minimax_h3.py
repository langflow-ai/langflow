"""Minimax H3 generation component."""

from lfx_acedatacloud.components.base import AceGenerationComponent, generation_inputs


class MiniMaxH3GenerateComponent(AceGenerationComponent):
    display_name = "MiniMax H3 Generate"
    description = "Run the Ace Data Cloud MiniMax H3 first-run API action."
    icon = "Bot"
    service_name = "minimax_h3"
    inputs = generation_inputs("minimax_h3")
