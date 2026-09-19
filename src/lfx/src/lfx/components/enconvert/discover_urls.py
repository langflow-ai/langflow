"""Discover URLs — map or crawl a site into a list of URLs."""

from __future__ import annotations

import requests
from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
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
    resp = requests.post(
        BASE_URL + endpoint, json=payload, headers={"X-API-Key": api_key}, timeout=TIMEOUT
    )
    if resp.status_code in (401, 403):
        raise ValueError(
            f"EnConvert rejected the API key (HTTP {resp.status_code}). Use a private "
            "key (sk_...); public pk_ keys are not accepted."
        )
    resp.raise_for_status()
    return resp.json()


def _csv(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()] if raw else []


class EnConvertDiscoverUrls(Component):
    display_name = "Discover URLs"
    description = "Map a site via sitemap, crawl, or hybrid, and return the discovered URLs."
    documentation = "https://www.enconvert.com/docs"
    icon = "Compass"
    name = "enconvert_discover_urls"  # stable internal id — do not rename

    inputs = [
        MessageTextInput(
            name="url",
            display_name="URL",
            required=True,
            info="The site to discover URLs from.",
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=["hybrid", "sitemap", "crawl"],
            value="hybrid",
        ),
        IntInput(name="max_urls", display_name="Max URLs", value=100),
        IntInput(name="max_depth", display_name="Max depth", value=2),
        MessageTextInput(
            name="include_patterns",
            display_name="Include patterns",
            info="Optional comma-separated glob patterns to keep.",
            advanced=True,
        ),
        MessageTextInput(
            name="exclude_patterns",
            display_name="Exclude patterns",
            info="Optional comma-separated glob patterns to drop.",
            advanced=True,
        ),
        BoolInput(
            name="same_domain_only",
            display_name="Same domain only",
            value=True,
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
        payload: dict = {
            "url": self.url,
            "mode": self.mode,
            "max_urls": self.max_urls,
            "max_depth": self.max_depth,
            "same_domain_only": self.same_domain_only,
        }
        include = _csv(self.include_patterns)
        exclude = _csv(self.exclude_patterns)
        if include:
            payload["include_patterns"] = include
        if exclude:
            payload["exclude_patterns"] = exclude
        result = _post("/v2/discover", self.api_key, payload)
        self.status = f"{result.get('total', len(result.get('urls', [])))} URLs"
        return Data(data=result)
