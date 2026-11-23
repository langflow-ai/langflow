"""Generate or edit images with WaveSpeed image models."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.wavespeed.wavespeed_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    WaveSpeedAPIError,
    clean_model_id,
    http_url,
    parse_extra_input,
    run_prediction,
)

DEFAULT_MODEL = "bytedance/seedream-v5.5"
DEFAULT_EDIT_MODEL = "bytedance/seedream-v5.5/edit"
MAX_EDIT_IMAGES = 10
DEFAULT_TIMEOUT_SECONDS = 300.0
# "auto" leaves the field out of the request, so the model applies its own default.
AUTO = "auto"
ASPECT_RATIOS = [
    AUTO,
    "1:1",
    "1:2",
    "2:1",
    "1:3",
    "3:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "9:21",
    "21:9",
]
RESOLUTIONS = [AUTO, "1k", "1.5k", "2k"]


class WaveSpeedImageGenerationComponent(Component):
    """Generate an image from a prompt, or edit input images, with a WaveSpeed image model.

    With the default model, input image URLs switch the run to the model's edit variant.
    """

    display_name = "WaveSpeed Image Generation"
    description = "Generate images from a text prompt, or edit input images, with WaveSpeed image models."
    documentation = DOCUMENTATION_URL
    icon = "Image"
    name = "WaveSpeedImageGeneration"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="WaveSpeed API Key",
            info=API_KEY_INFO,
            value="WAVESPEED_API_KEY",
            required=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="Describe the image to generate, or the change to make to the input images.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="image_urls",
            display_name="Image URLs",
            info=(
                "Optional http(s) URLs of images to edit, sent as the model's images input. "
                f"With the default model, they switch the run to {DEFAULT_EDIT_MODEL} "
                f"(up to {MAX_EDIT_IMAGES} images)."
            ),
            is_list=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="model",
            display_name="Model",
            info=(
                f"WaveSpeed model id, such as {DEFAULT_MODEL}. "
                "Any image model from the WaveSpeed catalog can be used; see https://wavespeed.ai/models."
            ),
            value=DEFAULT_MODEL,
        ),
        DropdownInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            info="Aspect ratio of the image. 'auto' leaves it to the model's default.",
            options=ASPECT_RATIOS,
            value=AUTO,
            combobox=True,
        ),
        DropdownInput(
            name="resolution",
            display_name="Resolution",
            info="Output resolution. 'auto' leaves it to the model's default.",
            options=RESOLUTIONS,
            value=AUTO,
            combobox=True,
        ),
        MultilineInput(
            name="extra_input",
            display_name="Extra Input",
            info='Optional JSON object of additional model inputs, such as {"output_format": "jpeg"}.',
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for the image before giving up.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Image", name="image", method="generate_image"),
    ]

    def _model_and_payload(self) -> tuple[str, dict[str, Any]]:
        prompt = str(self.prompt or "").strip()
        if not prompt:
            msg = "Enter a prompt describing the image."
            raise WaveSpeedAPIError(msg)
        raw_urls = self.image_urls if isinstance(self.image_urls, list) else [self.image_urls]
        image_urls = [http_url(url, "Each image URL") for url in raw_urls if str(url or "").strip()]

        model_id = clean_model_id(self.model, DEFAULT_MODEL)
        payload: dict[str, Any] = {"prompt": prompt}
        if image_urls:
            if model_id == DEFAULT_MODEL:
                model_id = DEFAULT_EDIT_MODEL
            if model_id == DEFAULT_EDIT_MODEL and len(image_urls) > MAX_EDIT_IMAGES:
                msg = f"{DEFAULT_EDIT_MODEL} accepts up to {MAX_EDIT_IMAGES} images; got {len(image_urls)}."
                raise WaveSpeedAPIError(msg)
            payload["images"] = image_urls
        for field in ("aspect_ratio", "resolution"):
            value = str(getattr(self, field, "") or "").strip()
            if value and value != AUTO:
                payload[field] = value
        payload.update(parse_extra_input(self.extra_input))
        return model_id, payload

    async def generate_image(self) -> Data:
        """Return the generated image URLs; ``image_url`` holds the first one."""
        try:
            model_id, payload = self._model_and_payload()
            prediction_id, outputs = await run_prediction(
                model_id,
                payload,
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
            )
        except WaveSpeedAPIError as exc:
            await logger.aerror(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})

        result = Data(
            text=outputs[0],
            data={"image_url": outputs[0], "image_urls": outputs, "model": model_id, "prediction_id": prediction_id},
        )
        self.status = outputs[0]
        return result
