import contextlib

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

try:
    from lfx.components.resemble._resemble_api import TERMINAL, item, poll, request, sanitize
except Exception:  # noqa: BLE001
    from _resemble_api import TERMINAL, item, poll, request, sanitize


class ResembleIntelligenceComponent(Component):
    display_name = "Resemble Media Intelligence"
    description = "Transcription, translation, speaker info, emotion, and misinformation analysis."
    documentation = "https://docs.resemble.ai"
    icon = "ScanSearch"
    name = "ResembleIntelligence"

    inputs = [
        SecretStrInput(name="api_key", display_name="Resemble API Key", required=True),
        MessageTextInput(
            name="url",
            display_name="Media URL",
            required=True,
            tool_mode=True,
            info="Public HTTPS URL to the media to analyze.",
        ),
        BoolInput(name="structured_json", display_name="Structured JSON", value=True, advanced=True),
        DropdownInput(
            name="media_type",
            display_name="Media Type",
            options=["auto", "audio", "video", "image"],
            value="auto",
            advanced=True,
        ),
        IntInput(name="max_wait_seconds", display_name="Max Wait (seconds)", value=120, advanced=True),
        MessageTextInput(name="base_url", display_name="API Base URL", value="", advanced=True),
    ]

    outputs = [Output(display_name="Analysis", name="analysis", method="run_intelligence")]

    def run_intelligence(self) -> Data:
        url = (self.url or "").strip()
        if not url:
            msg = "Media URL is required (a public HTTPS link)."
            raise ValueError(msg)
        body = {"url": url, "json": bool(getattr(self, "structured_json", True))}
        if getattr(self, "media_type", "auto") not in (None, "", "auto"):
            body["media_type"] = self.media_type

        result = request(self.api_key, self.base_url, "POST", "/intelligence", body)
        uuid = item(result).get("uuid")
        status = str(item(result).get("status") or "").lower()
        if uuid and status and status not in TERMINAL:
            # Poll path may vary by deployment; on failure return the submit payload.
            with contextlib.suppress(ValueError):
                result = poll(self.api_key, self.base_url, f"/intelligence/{uuid}", self.max_wait_seconds)
        data = Data(data=sanitize(result))
        self.status = data
        return data
