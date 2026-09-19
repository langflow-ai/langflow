"""Extract Structured (distill) — pull typed data from pages against a schema."""

from __future__ import annotations

import json

import requests

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
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


def _csv(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()] if raw else []


class EnConvertExtractStructured(Component):
    display_name = "Extract Structured"
    description = (
        "Extract structured data from one or more pages against a JSON schema "
        "(or a flat field:description map). Give either URLs or a site to discover from."
    )
    documentation = "https://www.enconvert.com/docs"
    icon = "Braces"
    name = "enconvert_extract_structured"  # stable internal id — do not rename

    inputs = [
        MultilineInput(
            name="extraction_schema",
            display_name="Schema",
            required=True,
            info=('A JSON schema {"type":"object","properties":{...}} OR a flat {"field":"description"} map.'),
        ),
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="Comma-separated page URLs (max 50). Provide this OR 'Discover from URL'.",
        ),
        MessageTextInput(
            name="discover_from_url",
            display_name="Discover from URL",
            info="A site to discover pages from, instead of listing URLs.",
        ),
        IntInput(
            name="discover_max_pages",
            display_name="Discover max pages",
            value=25,
            advanced=True,
            info="Only used with 'Discover from URL'.",
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
        urls = _csv(self.urls)
        discover = (self.discover_from_url or "").strip()
        if bool(urls) == bool(discover):
            raise ValueError("Provide exactly one of 'URLs' or 'Discover from URL' (not both, not neither).")
        raw_schema = (self.extraction_schema or "").strip()
        if not raw_schema:
            raise ValueError("Provide a JSON schema or a flat {field: description} map.")
        payload: dict = {"schema": json.loads(raw_schema)}
        if urls:
            payload["urls"] = urls
        else:
            discover_from: dict = {"url": discover}
            if self.discover_max_pages:
                discover_from["max_pages"] = self.discover_max_pages
            payload["discover_from"] = discover_from
        result = _post("/v2/distill", self.api_key, payload)
        self.status = f"tier={result.get('extraction_tier')}"
        return Data(data=result)
