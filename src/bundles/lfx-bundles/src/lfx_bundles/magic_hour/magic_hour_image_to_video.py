from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output

from lfx_bundles.magic_hour._api import create_project, download_urls, resolve_image_asset, wait_for_project
from lfx_bundles.magic_hour.magic_hour_text_to_video import VIDEO_MODELS, VIDEO_RESOLUTIONS


class MagicHourImageToVideoComponent(Component):
    display_name = "Magic Hour Image to Video"
    description = (
        "Animate an image into a video with Magic Hour. Accepts a public image URL or a local file path "
        "(uploaded automatically). wan-2.2, ltx-2.3 and minimax-h3 are free-tier models; "
        "premium models cost 30-120 credits/s. Returns the rendered video URL."
    )
    documentation = "https://docs.magichour.ai"
    icon = "Clapperboard"
    name = "MagicHourImageToVideo"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Magic Hour API Key",
            required=True,
            info="Your Magic Hour API key (free at https://magichour.ai/developer).",
        ),
        MessageTextInput(
            name="image",
            display_name="Image URL or Path",
            required=True,
            info="Public https URL of the source image, or a local file path to upload.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="Describe the motion or scene for the video.",
            tool_mode=True,
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=VIDEO_MODELS,
            value="wan-2.2",
            info="Video model. wan-2.2 / ltx-2.3 / minimax-h3 are free-tier (24 credits/s).",
        ),
        IntInput(
            name="duration",
            display_name="Duration (seconds)",
            value=5,
            info="Length of the video in seconds. Allowed values depend on the model.",
        ),
        DropdownInput(
            name="resolution",
            display_name="Resolution",
            options=VIDEO_RESOLUTIONS,
            value="480p",
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
            "name": f"Langflow: {(self.prompt or 'image to video')[:60]}",
            "model": self.model,
            "end_seconds": float(self.duration),
            "resolution": self.resolution,
            "style": {"prompt": self.prompt or ""},
            "assets": {"image_file_path": resolve_image_asset(self.api_key, self.image)},
        }

    def generate_video(self) -> Data:
        created = create_project(self.api_key, "image-to-video", self._build_payload())
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
            )
        self.status = result
        return Data(data=result)

    def video_url_message(self) -> Message:
        data = self.generate_video()
        return Message(text=data.data.get("video_url") or data.data["project_id"])
