"""Web Search — search the web (or news/images/scholar/patents/maps) via EnConvert."""

from __future__ import annotations

import requests

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

BASE_URL = "https://api.enconvert.com"
TIMEOUT = 120


def _post(endpoint: str, api_key: str, payload: dict) -> dict:
    """POST JSON to an EnConvert endpoint with the private-key header, return parsed JSON.

    Inlined per component: the Langflow loader imports bundle files standalone, so
    relative imports between them are unsupported.
    """
    if not api_key:
        raise ValueError(
            "EnConvert API key is missing. Add your private key (starts with sk_) "
            "from https://www.enconvert.com/dashboard/api-keys."
        )
    resp = requests.post(BASE_URL + endpoint, json=payload, headers={"X-API-Key": api_key}, timeout=TIMEOUT)
    if resp.status_code in (401, 403):
        raise ValueError(
            f"EnConvert rejected the API key (HTTP {resp.status_code}). Use a private "
            "key (sk_...); public pk_ keys are not accepted."
        )
    resp.raise_for_status()
    return resp.json()


class EnConvertWebSearch(Component):
    display_name = "Web Search"
    description = "Search the web and get back structured results (title, url, snippet, position)."
    documentation = "https://www.enconvert.com/docs"
    icon = "Search"
    name = "enconvert_web_search"  # stable internal id — do not rename

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Query",
            required=True,
            info="The search query.",
        ),
        DropdownInput(
            name="category",
            display_name="Category",
            options=["web", "news", "images", "scholar", "patents", "maps"],
            value="web",
        ),
        IntInput(
            name="num_results",
            display_name="Results",
            value=10,
            info="Number of results to return.",
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            info="Optional ISO country code (e.g. us).",
            advanced=True,
        ),
        MessageTextInput(
            name="locale",
            display_name="Locale",
            info="Optional locale (e.g. en).",
            advanced=True,
        ),
        DropdownInput(
            name="time_filter",
            display_name="Time filter",
            options=["", "hour", "day", "week", "month", "year"],
            value="",
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="EnConvert API Key",
            required=True,
            info="Private key (sk_...) from https://www.enconvert.com/dashboard/api-keys.",
        ),
    ]

    outputs = [Output(display_name="Data", name="data", method="build")]

    def build(self) -> Data:
        payload: dict = {"query": self.query, "category": self.category}
        if self.num_results:
            payload["num_results"] = self.num_results
        if self.country:
            payload["country"] = self.country
        if self.locale:
            payload["locale"] = self.locale
        if self.time_filter:
            payload["time_filter"] = self.time_filter
        result = _post("/v2/search", self.api_key, payload)
        self.status = f"{len(result.get('results', []))} results"
        return Data(data=result)
