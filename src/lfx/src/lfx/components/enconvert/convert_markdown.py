"""Convert File to Markdown — any file URL into clean markdown."""

from __future__ import annotations

import io

import requests

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

BASE_URL = "https://api.enconvert.com"
TIMEOUT = 120


def _convert(endpoint: str, api_key: str, file_url: str) -> dict:
    """Fetch file_url bytes (NO api key on that GET), then POST as multipart ``file``.

    Agent platforms hand tools a URL, not a local path, so the source fetch — and any
    presigned result URL — are retrieved without the api-key header; only the EnConvert
    POST carries X-API-Key. Inlined per component (bundle files are imported standalone).
    """
    if not api_key:
        raise ValueError(
            "EnConvert API key is missing. Add your private key (starts with sk_) "
            "from https://www.enconvert.com/dashboard/api-keys."
        )
    if not file_url:
        raise ValueError("Provide a file URL to convert.")
    src = requests.get(file_url, timeout=TIMEOUT)  # no api-key header on the source fetch
    src.raise_for_status()
    filename = file_url.split("?", 1)[0].rsplit("/", 1)[-1] or "file"
    resp = requests.post(
        BASE_URL + endpoint,
        files={"file": (filename, io.BytesIO(src.content))},
        headers={"X-API-Key": api_key},
        timeout=TIMEOUT,
    )
    if resp.status_code in (401, 403):
        raise ValueError(
            f"EnConvert rejected the API key (HTTP {resp.status_code}). Use a private "
            "key (sk_...); public pk_ keys are not accepted."
        )
    resp.raise_for_status()
    return resp.json()


class EnConvertConvertToMarkdown(Component):
    display_name = "Convert File to Markdown"
    description = (
        "Convert any file (from a URL) into clean markdown. The file bytes are fetched "
        "from the URL, converted, and returned as a presigned download URL."
    )
    documentation = "https://www.enconvert.com/docs"
    icon = "FileText"
    name = "enconvert_convert_to_markdown"  # stable internal id — do not rename

    inputs = [
        MessageTextInput(
            name="file_url",
            display_name="File URL",
            required=True,
            info="URL of the file to convert. Fetched without your api key.",
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
        result = _convert("/v1/convert/anything-to-markdown", self.api_key, self.file_url)
        self.status = result.get("presigned_url", "done")
        return Data(data=result)
