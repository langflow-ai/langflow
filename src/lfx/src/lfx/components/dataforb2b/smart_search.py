"""DataForB2B — Smart (natural-language) Search component for Langflow.

Wraps POST /search/reasoning: describe an ICP in plain English and get matching
people or companies. Handles the ``needs_input`` clarifying-question flow.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from ._client import DataForB2BClient, parse_json_filters


class DataForB2BSmartSearchComponent(Component):
    display_name = "Smart Search"
    description = (
        "Natural-language search for people, leads or companies using DataForB2B's "
        "B2B database — describe your ideal lead or ICP in plain English (e.g. "
        "'marketing directors at Series A SaaS startups in France') and get matching "
        "profiles with LinkedIn URL, email and firmographics. Handles clarifying "
        "questions."
    )
    documentation = "https://docs.dataforb2b.ai"
    icon = "DataForB2B"
    name = "DataForB2BSmartSearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="DataForB2B API Key",
            required=True,
            info="Your DataForB2B API key (header api_key). Get one at https://app.dataforb2b.ai.",
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            value="",
            tool_mode=True,
            info="Plain-English search / ICP description.",
        ),
        DropdownInput(
            name="category",
            display_name="Category",
            options=["people", "company"],
            value="people",
            info="What to search for: people or company.",
        ),
        IntInput(
            name="max_results",
            display_name="Max results",
            value=25,
        ),
        BoolInput(
            name="enrich_live",
            display_name="Live enrichment",
            value=False,
            advanced=True,
            info="Fetch fresh live data (uses more credits).",
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            value="",
            advanced=True,
            info="Session id to resolve a previous 'needs_input' turn.",
        ),
        MultilineInput(
            name="answers",
            display_name="Answers (JSON)",
            value="",
            advanced=True,
            info="Answers to clarifying questions, e.g. {\"question_id\": \"answer\"}.",
        ),
    ]

    outputs = [
        Output(display_name="Results", name="results", method="search"),
        Output(display_name="Raw response", name="raw", method="raw_response"),
    ]

    def _run(self) -> dict:
        if not self.query and not self.session_id:
            msg = "Provide 'query' (first call) or 'session_id' + 'answers' (to resolve a needs_input turn)."
            raise ValueError(msg)
        payload: dict = {
            "category": self.category or "people",
            "max_results": int(self.max_results or 25),
            "enrich_live": bool(self.enrich_live),
        }
        if self.query:
            payload["query"] = self.query
        if self.session_id:
            payload["session_id"] = self.session_id
        answers = parse_json_filters(self.answers)
        if answers:
            payload["answers"] = answers

        data = DataForB2BClient(self.api_key).reasoning_search(payload)
        self._cached = data
        return data

    def search(self) -> DataFrame:
        data = getattr(self, "_cached", None) or self._run()
        results = data.get("results", []) or []
        status = data.get("status", "ok")
        self.status = (
            "needs_input — see Raw response for clarifying questions"
            if status == "needs_input"
            else f"{data.get('total', len(results))} match(es)"
        )
        return DataFrame([Data(data=r) for r in results])

    def raw_response(self) -> Data:
        data = getattr(self, "_cached", None) or self._run()
        return Data(data=data)
