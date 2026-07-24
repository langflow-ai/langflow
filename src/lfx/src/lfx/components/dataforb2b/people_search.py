"""DataForB2B — LinkedIn People / B2B Lead Search component for Langflow."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from ._client import PEOPLE_COLUMNS, DataForB2BClient, build_filters
from ._filter_inputs import common_search_inputs, filter_slot_inputs, read_slots


class DataForB2BPeopleSearchComponent(Component):
    display_name = "Search People"
    description = (
        "Search people and B2B leads by structured filters — job title, company, "
        "location, industry, seniority, skills, LinkedIn URL — using DataForB2B's "
        "database. Find employees at a company, decision-makers and key contacts "
        "(founders, C-suite, VPs, directors) and build a prospect or lead list. "
        "The lead-sourcing step of a prospecting or outreach workflow."
    )
    documentation = "https://docs.dataforb2b.ai"
    icon = "DataForB2B"
    name = "DataForB2BPeopleSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="DataForB2B API Key",
            required=True,
            info="Your DataForB2B API key (header api_key). Get one at https://app.dataforb2b.ai.",
        ),
        *filter_slot_inputs(PEOPLE_COLUMNS),
        *common_search_inputs(),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="search"),
        Output(display_name="Raw response", name="raw", method="raw_response"),
    ]

    def _run(self) -> dict:
        filters = build_filters(read_slots(self), self.match, self.filters_json)
        payload = {
            "filters": filters,
            "count": int(self.count or 25),
            "offset": int(self.offset or 0),
            "enrich_live": bool(self.enrich_live),
        }
        data = DataForB2BClient(self.api_key).search_people(payload)
        self._cached = data
        return data

    def search(self) -> DataFrame:
        data = getattr(self, "_cached", None) or self._run()
        results = data.get("results", []) or []
        self.status = f"{data.get('total', len(results))} match(es)"
        return DataFrame([Data(data=r) for r in results])

    def raw_response(self) -> Data:
        data = getattr(self, "_cached", None) or self._run()
        return Data(data=data)
