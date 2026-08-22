from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.template.field.base import Output

from lfx_bundles.magic_hour._api import create_project, download_urls, wait_for_project

IMAGE_MODELS = [
    "default",
    "gpt-image-2",
    "nano-banana-pro",
    "seedream-5-pro",
    "flux-2-klein",
    "z-image-turbo",
    "qwen-edit",
]
IMAGE_ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"]


class MagicHourImageGeneratorComponent(Component):
    display_name = "Magic Hour Image Generator"
    description = (
        "Generate images from a text prompt with Magic Hour (GPT-image, Nano Banana Pro, Seedream, Flux, Z-Image). "
        "Costs 5 credits per image with the default model. Returns the image URLs."
    )
    documentation = "https://docs.magichour.ai"
    icon = "Clapperboard"
    name = "MagicHourImageGenerator"

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
            info="Describe the image to generate.",
            tool_mode=True,
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=IMAGE_MODELS,
            value="default",
            info="Image model. 'default' is the cheapest; nano-banana-pro / gpt-image-2 give the highest quality.",
        ),
        IntInput(
            name="image_count",
            display_name="Image Count",
            value=1,
            info="Number of images to generate (1-4).",
        ),
        DropdownInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            options=IMAGE_ASPECT_RATIOS,
            value="1:1",
        ),
        BoolInput(
            name="wait_for_completion",
            display_name="Wait for Completion",
            value=True,
            advanced=True,
            info="Poll until rendering finishes. If off, only the project id is returned.",
        ),
        IntInput(
            name="timeout_seconds",
            display_name="Timeout (seconds)",
            value=300,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="generate_images"),
        Output(display_name="Image URL", name="image_url", method="image_url_message"),
    ]

    def _build_payload(self) -> dict:
        return {
            "name": f"Langflow: {self.prompt[:60]}",
            "model": self.model,
            "image_count": int(self.image_count or 1),
            "aspect_ratio": self.aspect_ratio,
            "style": {"prompt": self.prompt},
        }

    def generate_images(self) -> Data:
        created = create_project(self.api_key, "ai-image-generator", self._build_payload())
        result = {
            "project_id": created["id"],
            "status": "queued",
            "image_urls": [],
            "credits_charged": created.get("credits_charged"),
            "model": self.model,
        }
        if self.wait_for_completion:
            project = wait_for_project(self.api_key, "image", created["id"], timeout=float(self.timeout_seconds or 300))
            result.update(
                status=project.get("status"),
                image_urls=download_urls(project),
                credits_charged=project.get("credits_charged", result["credits_charged"]),
            )
        self.status = result
        return Data(data=result)

    def image_url_message(self) -> Message:
        data = self.generate_images()
        urls = data.data.get("image_urls") or []
        return Message(text=urls[0] if urls else data.data["project_id"])
