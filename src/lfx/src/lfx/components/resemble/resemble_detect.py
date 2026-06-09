from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

try:  # package import when installed as part of lfx
    from lfx.components.resemble._resemble_api import item, poll, request, sanitize
except Exception:  # noqa: BLE001 — dev/test fallback (bundle dir on sys.path)
    from _resemble_api import item, poll, request, sanitize


class ResembleDetectComponent(Component):
    display_name = "Resemble Deepfake Detection"
    description = "Detect AI-generated / manipulated audio, image, or video with Resemble AI."
    documentation = "https://docs.resemble.ai"
    icon = "ShieldCheck"
    name = "ResembleDetect"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Resemble API Key",
            required=True,
            info="Your Resemble API key (dashboard → Account → API).",
        ),
        MessageTextInput(
            name="url",
            display_name="Media URL",
            required=True,
            tool_mode=True,
            info="Public HTTPS URL to the audio, image, or video to analyze.",
        ),
        BoolInput(
            name="run_intelligence",
            display_name="Run Intelligence",
            value=False,
            advanced=True,
            info="Also run multimodal intelligence analysis.",
        ),
        BoolInput(
            name="audio_source_tracing",
            display_name="Audio Source Tracing",
            value=False,
            advanced=True,
            info="If audio is fake, identify the generating platform.",
        ),
        BoolInput(
            name="visualize", display_name="Visualize", value=False, advanced=True, info="Generate heatmap artifacts."
        ),
        BoolInput(
            name="use_reverse_search",
            display_name="Reverse Image Search",
            value=False,
            advanced=True,
            info="Image only — search the web for known sources.",
        ),
        BoolInput(name="use_ood_detector", display_name="Out-of-Distribution Detector", value=False, advanced=True),
        BoolInput(
            name="zero_retention_mode",
            display_name="Zero-Retention Mode",
            value=False,
            advanced=True,
            info="Auto-delete media after analysis.",
        ),
        DropdownInput(
            name="model_types",
            display_name="Model Type",
            options=["auto", "image", "talking_head"],
            value="auto",
            advanced=True,
        ),
        IntInput(name="max_wait_seconds", display_name="Max Wait (seconds)", value=120, advanced=True),
        MessageTextInput(
            name="base_url",
            display_name="API Base URL",
            value="",
            advanced=True,
            info="Override only for self-hosted / enterprise.",
        ),
    ]

    outputs = [Output(display_name="Result", name="result", method="run_detection")]

    def run_detection(self) -> Data:
        url = (self.url or "").strip()
        if not url:
            msg = "Media URL is required (a public HTTPS link)."
            raise ValueError(msg)
        body = {"url": url}
        for attr, key in (
            ("run_intelligence", "intelligence"),
            ("audio_source_tracing", "audio_source_tracing"),
            ("visualize", "visualize"),
            ("use_reverse_search", "use_reverse_search"),
            ("use_ood_detector", "use_ood_detector"),
            ("zero_retention_mode", "zero_retention_mode"),
        ):
            if getattr(self, attr, False):
                body[key] = True
        if getattr(self, "model_types", "auto") not in (None, "", "auto"):
            body["model_types"] = self.model_types

        submitted = request(self.api_key, self.base_url, "POST", "/detect", body)
        uuid = item(submitted).get("uuid")
        result = poll(self.api_key, self.base_url, f"/detect/{uuid}", self.max_wait_seconds) if uuid else submitted
        data = Data(data=sanitize(result))
        self.status = data
        return data
