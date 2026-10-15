"""DataForB2B — Typeahead component for Langflow.

Resolves the exact stored value for a free-text filter (company, industry,
title, skill, school, investor, location, category) before searching.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from ._client import TYPEAHEAD_TYPES, DataForB2BClient


class DataForB2BTypeaheadComponent(Component):
    display_name = "Typeahead"
    description = (
        "Resolve the exact filter value (company, industry, job title, skill, "
        "school, location, LinkedIn URL) for people and company searches with "
        "DataForB2B. Use it to normalize free text before a structured search."
    )
    documentation = "https://docs.dataforb2b.ai"
    icon = "DataForB2B"
    name = "DataForB2BTypeahead"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="DataForB2B API Key",
            required=True,
            info="Your DataForB2B API key (header api_key). Get one at https://app.dataforb2b.ai.",
        ),
        DropdownInput(
            name="type",
            display_name="Type",
            options=TYPEAHEAD_TYPES,
            value="company",
            info="Filter type to resolve.",
        ),
        MessageTextInput(
            name="q",
            display_name="Query",
            value="",
            tool_mode=True,
            info="Free-text query to resolve to a stored value.",
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=20,
            info="Max suggestions (1-20).",
        ),
    ]

    outputs = [
        Output(display_name="Suggestions", name="suggestions", method="resolve"),
        Output(display_name="Raw response", name="raw", method="raw_response"),
    ]

    def _run(self) -> dict:
        if not self.q:
            msg = "'q' (query) is required."
            raise ValueError(msg)
        limit = max(1, min(int(self.limit or 20), 20))
        data = DataForB2BClient(self.api_key).typeahead(self.type or "company", self.q, limit)
        self._cached = data
        return data

    def resolve(self) -> DataFrame:
        data = getattr(self, "_cached", None) or self._run()
        results = data.get("results", []) or []
        self.status = f"{len(results)} suggestion(s)"
        return DataFrame([Data(data=r) for r in results])

    def raw_response(self) -> Data:
        data = getattr(self, "_cached", None) or self._run()
        return Data(data=data)
