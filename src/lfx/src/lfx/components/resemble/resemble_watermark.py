import contextlib

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

try:
    from lfx.components.resemble._resemble_api import item, poll, request, sanitize
except Exception:  # noqa: BLE001
    from _resemble_api import item, poll, request, sanitize


class ResembleWatermarkComponent(Component):
    display_name = "Resemble Watermark"
    description = "Apply or detect an invisible Resemble provenance watermark (audio-first)."
    documentation = "https://docs.resemble.ai"
    icon = "Fingerprint"
    name = "ResembleWatermark"

    inputs = [
        SecretStrInput(name="api_key", display_name="Resemble API Key", required=True),
        DropdownInput(
            name="operation",
            display_name="Operation",
            options=["detect", "apply"],
            value="detect",
            info="Detect a watermark, or apply one and return the watermarked media.",
        ),
        MessageTextInput(
            name="url", display_name="Media URL", required=True, tool_mode=True, info="Public HTTPS URL to the media."
        ),
        FloatInput(
            name="strength",
            display_name="Strength (apply)",
            value=0.2,
            advanced=True,
            info="Watermark strength 0.0-1.0 (image/video only).",
        ),
        MessageTextInput(
            name="custom_message",
            display_name="Custom Message (apply)",
            value="",
            advanced=True,
            info="Message to embed; defaults to 'resembleai'.",
        ),
        IntInput(name="max_wait_seconds", display_name="Max Wait (seconds)", value=120, advanced=True),
        MessageTextInput(name="base_url", display_name="API Base URL", value="", advanced=True),
    ]

    outputs = [Output(display_name="Result", name="result", method="run_watermark")]

    def run_watermark(self) -> Data:
        url = (self.url or "").strip()
        if not url:
            msg = "Media URL is required (a public HTTPS link)."
            raise ValueError(msg)
        op = getattr(self, "operation", "detect")
        try:
            if op == "apply":
                body = {"url": url}
                if getattr(self, "strength", None) not in (None, ""):
                    body["strength"] = float(self.strength)
                if (getattr(self, "custom_message", "") or "").strip():
                    body["custom_message"] = self.custom_message.strip()
                result = request(
                    self.api_key, self.base_url, "POST", "/watermark/apply", body, extra_headers={"Prefer": "wait"}
                )
                it = item(result)
                if not (it.get("watermarked_media") or it.get("url")) and it.get("uuid"):
                    with contextlib.suppress(ValueError):
                        result = poll(
                            self.api_key, self.base_url, f"/watermark/apply/{it['uuid']}/result", self.max_wait_seconds
                        )
            else:
                result = request(
                    self.api_key,
                    self.base_url,
                    "POST",
                    "/watermark/detect",
                    {"url": url},
                    extra_headers={"Prefer": "wait"},
                )
        except ValueError as exc:
            if "internal error" in str(exc).lower():
                msg = f"{exc} — watermarking works reliably for audio; some image/video inputs are not supported."
                raise ValueError(msg) from exc
            raise

        data = Data(data=sanitize(result))
        self.status = data
        return data
