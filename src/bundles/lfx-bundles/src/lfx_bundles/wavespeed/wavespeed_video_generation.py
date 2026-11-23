"""Generate videos with WaveSpeed video models."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.wavespeed.wavespeed_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    WaveSpeedAPIError,
    clean_model_id,
    error_data,
    http_url,
    parse_extra_input,
    run_prediction,
)

DEFAULT_MODEL = "alibaba/wan-3.0/text-to-video"
DEFAULT_IMAGE_MODEL = "alibaba/wan-3.0/image-to-video"
DEFAULT_DURATION_SECONDS = 5
DEFAULT_TIMEOUT_SECONDS = 900.0
# "auto" leaves the field out of the request, so the model applies its own default.
AUTO = "auto"
ASPECT_RATIOS = [AUTO, "16:9", "9:16", "1:1", "4:3", "3:4"]
RESOLUTIONS = [AUTO, "480p", "720p", "1080p"]


class WaveSpeedVideoGenerationComponent(Component):
    """Generate a video from a prompt, or animate a first-frame image, with a WaveSpeed video model.

    With the default model, an image URL switches the run to the model's image-to-video variant.
    """

    display_name = "WaveSpeed Video Generation"
    description = "Generate videos from a text prompt or a first-frame image with WaveSpeed video models."
    documentation = DOCUMENTATION_URL
    icon = "Video"
    name = "WaveSpeedVideoGeneration"

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
            info="Describe the video to generate.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="image_url",
            display_name="Image URL",
            info=(
                "Optional http(s) URL of the first frame, sent as the model's image input. "
                f"With the default model, it switches the run to {DEFAULT_IMAGE_MODEL}."
            ),
            tool_mode=True,
        ),
        MessageTextInput(
            name="model",
            display_name="Model",
            info=(
                f"WaveSpeed model id, such as {DEFAULT_MODEL}. "
                "Any video model from the WaveSpeed catalog can be used; see https://wavespeed.ai/models."
            ),
            value=DEFAULT_MODEL,
        ),
        DropdownInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            info="Aspect ratio of the video. 'auto' leaves it to the model's default.",
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
        IntInput(
            name="duration",
            display_name="Duration (seconds)",
            info="Length of the video in seconds. Set 0 to leave it to the model's default.",
            value=DEFAULT_DURATION_SECONDS,
        ),
        MultilineInput(
            name="extra_input",
            display_name="Extra Input",
            info='Optional JSON object of additional model inputs, such as {"seed": 42}.',
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for the video before giving up.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Video", name="video", method="generate_video"),
    ]

    def _model_and_payload(self) -> tuple[str, dict[str, Any]]:
        prompt = str(self.prompt or "").strip()
        if not prompt:
            msg = "Enter a prompt describing the video."
            raise WaveSpeedAPIError(msg)
        model_id = clean_model_id(self.model, DEFAULT_MODEL)
        payload: dict[str, Any] = {"prompt": prompt}
        if str(self.image_url or "").strip():
            if model_id == DEFAULT_MODEL:
                model_id = DEFAULT_IMAGE_MODEL
            payload["image"] = http_url(self.image_url, "Image URL")
        for field in ("aspect_ratio", "resolution"):
            value = str(getattr(self, field, "") or "").strip()
            if value and value != AUTO:
                payload[field] = value
        if self.duration:
            payload["duration"] = int(self.duration)
        payload.update(parse_extra_input(self.extra_input))
        return model_id, payload

    async def generate_video(self) -> Data:
        """Return the generated video URLs; ``video_url`` holds the first one."""
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
            return Data(text=str(exc), data=error_data(exc))

        result = Data(
            text=outputs[0],
            data={"video_url": outputs[0], "video_urls": outputs, "model": model_id, "prediction_id": prediction_id},
        )
        self.status = outputs[0]
        return result
