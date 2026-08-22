from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output

from lfx_bundles.magic_hour._api import create_project, download_urls, wait_for_project

VIDEO_MODELS = [
    "wan-2.2",
    "ltx-2.3",
    "minimax-h3",
    "seedance-1.5",
    "seedance-2.0-mini",
    "seedance-2.0",
    "seedance-2.5",
    "kling-2.6",
    "kling-3.0",
    "veo3.1-lite",
    "veo3.1",
    "veo3.1-audio",
    "sora-2",
]
VIDEO_RESOLUTIONS = ["480p", "720p", "1080p"]
ASPECT_RATIOS = ["16:9", "9:16", "1:1"]


class MagicHourTextToVideoComponent(Component):
    display_name = "Magic Hour Text to Video"
    description = (
        "Generate a video from a text prompt with Magic Hour (Sora 2, Veo 3.1, Kling 3.0, Seedance, WAN 2.2, ...). "
        "wan-2.2, ltx-2.3 and minimax-h3 are free-tier models (24 credits/s); "
        "premium models cost 30-120 credits/s. Returns the rendered video URL."
    )
    documentation = "https://docs.magichour.ai"
    icon = "Clapperboard"
    name = "MagicHourTextToVideo"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Magic Hour API Key",
            required=True,
            info="Your Magic Hour API key (free at https://magichour.ai/developer).",
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            info="Describe the video to generate.",
            tool_mode=True,
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=VIDEO_MODELS,
            value="wan-2.2",
            info=(
                "Video model. wan-2.2 / ltx-2.3 / minimax-h3 are free-tier (24 credits/s); "
                "kling-3.0 is 48 credits/s, veo3.1 96 credits/s, sora-2 120 credits/s (max 720p)."
            ),
        ),
        IntInput(
            name="duration",
            display_name="Duration (seconds)",
            value=5,
            info="Length of the video in seconds. Allowed values depend on the model (wan-2.2: 3-10 or 15).",
        ),
        DropdownInput(
            name="resolution",
            display_name="Resolution",
            options=VIDEO_RESOLUTIONS,
            value="480p",
            info="Output resolution. sora-2 and seedance-2.x are limited to 720p.",
        ),
        DropdownInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            options=ASPECT_RATIOS,
            value="16:9",
            advanced=True,
        ),
        BoolInput(
            name="audio",
            display_name="Generate Audio",
            value=False,
            advanced=True,
            info="Ask the model to generate audio where supported (e.g. veo3.1-audio).",
        ),
        BoolInput(
            name="wait_for_completion",
            display_name="Wait for Completion",
            value=True,
            advanced=True,
            info="Poll until the render finishes. If off, only the project id is returned.",
        ),
        IntInput(
            name="timeout_seconds",
            display_name="Timeout (seconds)",
            value=900,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="generate_video"),
        Output(display_name="Video URL", name="video_url", method="video_url_message"),
    ]

    def _build_payload(self) -> dict:
        return {
            "name": f"Langflow: {self.prompt[:60]}",
            "model": self.model,
            "end_seconds": float(self.duration),
            "resolution": self.resolution,
            "aspect_ratio": self.aspect_ratio,
            "audio": bool(self.audio),
            "style": {"prompt": self.prompt},
        }

    def generate_video(self) -> Data:
        created = create_project(self.api_key, "text-to-video", self._build_payload())
        result = {
            "project_id": created["id"],
            "status": "queued",
            "video_url": None,
            "credits_charged": created.get("credits_charged"),
            "model": self.model,
        }
        if self.wait_for_completion:
            project = wait_for_project(self.api_key, "video", created["id"], timeout=float(self.timeout_seconds or 900))
            urls = download_urls(project)
            result.update(
                status=project.get("status"),
                video_url=urls[0] if urls else None,
                credits_charged=project.get("credits_charged", result["credits_charged"]),
                width=project.get("width"),
                height=project.get("height"),
                fps=project.get("fps"),
            )
        self.status = result
        return Data(data=result)

    def video_url_message(self) -> Message:
        data = self.generate_video()
        return Message(text=data.data.get("video_url") or data.data["project_id"])
