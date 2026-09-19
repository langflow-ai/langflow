"""Perceive URL — render a web page into agent-ready outputs with a quality score."""

from __future__ import annotations

import requests

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

BASE_URL = "https://api.enconvert.com"
TIMEOUT = 120


def _post(endpoint: str, api_key: str, payload: dict) -> dict:
    """POST JSON to an EnConvert endpoint with the private-key header, return parsed JSON.

    Bundle modules are imported standalone by the Langflow loader, so this helper is
    inlined per component (relative imports between bundle files are unsupported).
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


class EnConvertPerceive(Component):
    display_name = "Perceive URL"
    description = (
        "Render a web page into agent-ready outputs (markdown, structured data, "
        "screenshot, PDF, links...) with a render_quality honesty score on every read."
    )
    documentation = "https://www.enconvert.com/docs"
    icon = "Eye"
    name = "enconvert_perceive"  # stable internal id — do not rename

    inputs = [
        MessageTextInput(
            name="url",
            display_name="URL",
            required=True,
            info="The page to perceive.",
        ),
        MessageTextInput(
            name="formats",
            display_name="Outputs",
            value="markdown,structured",
            info=(
                "Comma-separated. Allowed: markdown, html_cleaned, html_raw, screenshot, "
                "screenshot_full_page, pdf, links, images, structured. markdown and "
                "structured come back inline; screenshot/pdf/html return 15-minute signed URLs."
            ),
        ),
        BoolInput(
            name="only_main_content",
            display_name="Only main content",
            value=False,
            info="Strip navigation and boilerplate, keep the main content.",
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
        payload: dict = {"url": self.url}
        formats = _csv(self.formats)
        if formats:
            payload["outputs"] = formats
        if self.only_main_content:
            payload["only_main_content"] = True
        result = _post("/v2/perceive", self.api_key, payload)
        self.status = f"render_quality={result.get('render_quality')}"
        return Data(data=result)
