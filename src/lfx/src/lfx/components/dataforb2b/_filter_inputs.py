"""Reusable input builders shared by the two structured-search components.

Keeps People Search and Company Search in parity: five (column, operator,
value) filter slots plus an advanced raw-JSON filter, mirroring the AutoGPT /
Dify integrations.
"""

from __future__ import annotations

from lfx.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
)

from ._client import OPERATORS

NUM_SLOTS = 5
VISIBLE_SLOTS = 2  # first slots shown by default, the rest collapsed under "advanced"


def filter_slot_inputs(columns: list[str]) -> list:
    """Build the (column, operator, value) dropdown/text inputs for each slot."""
    inputs: list = []
    for i in range(1, NUM_SLOTS + 1):
        advanced = i > VISIBLE_SLOTS  # first slots visible, rest collapsed
        inputs.append(
            DropdownInput(
                name=f"filter_{i}_column",
                display_name=f"Filter {i} column",
                options=["", *columns],
                value="",
                combobox=True,
                advanced=advanced,
                info="Column to filter on (leave empty to skip this slot).",
            )
        )
        inputs.append(
            DropdownInput(
                name=f"filter_{i}_operator",
                display_name=f"Filter {i} operator",
                options=OPERATORS,
                value="like",
                advanced=advanced,
                info="'like' for text match, 'in' for a comma list, 'between' for min,max.",
            )
        )
        inputs.append(
            MessageTextInput(
                name=f"filter_{i}_value",
                display_name=f"Filter {i} value",
                value="",
                advanced=advanced,
                tool_mode=True,
                info="Filter value. Comma-separated for 'in'; 'min,max' for 'between'.",
            )
        )
    return inputs


def common_search_inputs() -> list:
    """Inputs shared by both search components besides the filter slots."""
    return [
        MultilineInput(
            name="filters_json",
            display_name="Advanced filters (JSON)",
            value="",
            advanced=True,
            info=(
                "Raw filter JSON {op, conditions:[{column,type,value,value2?}]}. "
                "Paste 'applied_filters' from Smart Search to paginate. Used alone "
                "or merged (AND) with the filter slots above."
            ),
        ),
        DropdownInput(
            name="match",
            display_name="Match",
            options=["and", "or"],
            value="and",
            advanced=True,
            info="Combine the filter slots with AND or OR.",
        ),
        IntInput(
            name="count",
            display_name="Count",
            value=25,
            info="Number of results to return.",
        ),
        IntInput(
            name="offset",
            display_name="Offset",
            value=0,
            advanced=True,
            info="Pagination offset — 0 for page 1, then 25, 50, … to page through results.",
        ),
        BoolInput(
            name="enrich_live",
            display_name="Live enrichment",
            value=False,
            advanced=True,
            info="Fetch fresh live data (uses more credits).",
        ),
    ]


def read_slots(component) -> list[tuple]:
    """Read the five (column, operator, value) slots off a component instance."""
    return [
        (
            getattr(component, f"filter_{i}_column", ""),
            getattr(component, f"filter_{i}_operator", "like"),
            getattr(component, f"filter_{i}_value", ""),
        )
        for i in range(1, NUM_SLOTS + 1)
    ]
