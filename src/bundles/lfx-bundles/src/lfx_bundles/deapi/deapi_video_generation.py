"""Generate a short video from a text prompt with deAPI."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

from lfx_bundles.deapi.deapi_common import (
    API_KEY_INFO,
    DOCUMENTATION_URL,
    DeapiAPIError,
    error_payload,
    find_model,
    job_payload,
    model_info,
    model_slugs,
    pick_int,
    run_job,
)

INFERENCE_TYPE = "txt2video"
# Shown until the live catalog loads (it refreshes once an API key is set).
FALLBACK_MODELS = ["Ltx2_5_22B_Dist_INT8", "MiniMaxH3_33B_Turbo_INT8", "Ltx2_3_22B_Dist_INT8"]


class DeapiVideoGenerationComponent(Component):
    """Generate one video through deAPI and return its URL.

    Size, frame count, frame rate and steps come from the selected model's published
    defaults unless set, and are clamped to its published limits.
    """

    display_name = "deAPI Video Generation"
    description = "Generate a short video from a text prompt with open-source models on deAPI, such as LTX."
    documentation = DOCUMENTATION_URL
    icon = "deAPI"
    name = "DeapiVideoGeneration"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="deAPI API Key",
            info=API_KEY_INFO,
            required=True,
            value="DEAPI_API_KEY",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="A text description of the video to generate.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The deAPI model to use. The list shows the text-to-video models available to your account.",
            options=FALLBACK_MODELS,
            value=FALLBACK_MODELS[0],
            refresh_button=True,
            combobox=True,
        ),
        MessageTextInput(
            name="negative_prompt",
            display_name="Negative Prompt",
            info="What to avoid in the video. Ignored by models that do not support it.",
            advanced=True,
        ),
        IntInput(
            name="width",
            display_name="Width",
            info="Video width in pixels. Leave at 0 to use the model's default.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="height",
            display_name="Height",
            info="Video height in pixels. Leave at 0 to use the model's default.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="frames",
            display_name="Frames",
            info="Number of frames; the length is frames divided by the model's frame rate. "
            "Leave at 0 to use the model's default.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="Seed for reproducible results. Use -1 for a random seed.",
            value=-1,
            advanced=True,
        ),
        IntInput(
            name="max_wait",
            display_name="Max Wait (seconds)",
            info="How long to wait for the video before returning the job's request ID.",
            value=600,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Video", name="video", method="generate_video"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Reload the model list from the live catalog when the key changes or Refresh is pressed."""
        if field_name in {"api_key", "model_name"}:
            build_config["model_name"]["options"] = model_slugs(self.api_key, INFERENCE_TYPE, FALLBACK_MODELS)
        return build_config

    def build_payload(self) -> dict[str, Any]:
        """Build the request body, filling size, frames, frame rate and steps from the model."""
        prompt = str(self.prompt or "").strip()
        if not prompt:
            msg = "Enter a prompt."
            raise DeapiAPIError(msg)
        model = str(self.model_name or "").strip()
        if not model:
            msg = "Choose a model."
            raise DeapiAPIError(msg)
        defaults, limits = model_info(find_model(self.api_key, INFERENCE_TYPE, model))
        payload: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "width": pick_int(self.width, defaults.get("width"), limits.get("min_width"), limits.get("max_width")),
            "height": pick_int(self.height, defaults.get("height"), limits.get("min_height"), limits.get("max_height")),
            "frames": pick_int(self.frames, defaults.get("frames"), limits.get("min_frames"), limits.get("max_frames")),
            # The model dictates the frame rate; there is no input for it.
            "fps": pick_int(
                None, defaults.get("fps") or limits.get("min_fps"), limits.get("min_fps"), limits.get("max_fps")
            ),
            "seed": int(self.seed) if self.seed is not None else -1,
        }
        steps = defaults.get("steps") or limits.get("min_steps")
        if steps:
            payload["steps"] = pick_int(None, steps, limits.get("min_steps"), limits.get("max_steps"))
        negative_prompt = str(self.negative_prompt or "").strip()
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return payload

    def generate_video(self) -> Data:
        """Return the video as a ``Data`` whose ``text`` is the video URL (also under ``video_url``)."""
        try:
            job = run_job(
                "/videos/generations", self.build_payload(), api_key=self.api_key, max_wait_seconds=self.max_wait
            )
        except DeapiAPIError as exc:
            payload = error_payload(str(exc))
        else:
            payload = job_payload(job, kind="video", url_key="video_url")
        self.status = payload["text"]
        return Data(data=payload)
