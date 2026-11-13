"""Generate an image from a text prompt with deAPI."""

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

INFERENCE_TYPE = "txt2img"
# Shown until the live catalog loads (it refreshes once an API key is set).
FALLBACK_MODELS = ["Flux1schnell", "ZImageTurbo_INT8", "Flux_2_Klein_4B_BF16", "ZAnimeDistill_8Step_INT8"]
DEFAULT_STEPS = 4


class DeapiImageGenerationComponent(Component):
    """Generate one image through deAPI and return its URL.

    Width, height and steps fall back to the selected model's published defaults,
    and are clamped to its published limits, so switching models keeps working.
    """

    display_name = "deAPI Image Generation"
    description = "Generate an image from a text prompt with open-source models on deAPI, such as FLUX and Z-Image."
    documentation = DOCUMENTATION_URL
    icon = "deAPI"
    name = "DeapiImageGeneration"

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
            info="A text description of the image to generate.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The deAPI model to use. The list shows the text-to-image models available to your account.",
            options=FALLBACK_MODELS,
            value=FALLBACK_MODELS[0],
            refresh_button=True,
            combobox=True,
        ),
        MessageTextInput(
            name="negative_prompt",
            display_name="Negative Prompt",
            info="What to avoid in the image. Ignored by models that do not support it.",
            advanced=True,
        ),
        IntInput(
            name="width",
            display_name="Width",
            info="Image width in pixels. Leave at 0 to use the model's default.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="height",
            display_name="Height",
            info="Image height in pixels. Leave at 0 to use the model's default.",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="steps",
            display_name="Steps",
            info="Inference steps. Leave at 0 to use the model's default. Ignored by models that do not use steps.",
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
            info="How long to wait for the image before returning the job's request ID.",
            value=180,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Image", name="image", method="generate_image"),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Reload the model list from the live catalog when the key changes or Refresh is pressed."""
        if field_name in {"api_key", "model_name"}:
            build_config["model_name"]["options"] = model_slugs(self.api_key, INFERENCE_TYPE, FALLBACK_MODELS)
        return build_config

    def build_payload(self) -> dict[str, Any]:
        """Build the request body, filling sizes and steps from the model's defaults and limits."""
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
            # The API requires steps for models that use them and drops it for the others.
            "steps": pick_int(
                self.steps,
                defaults.get("steps") or limits.get("min_steps") or DEFAULT_STEPS,
                limits.get("min_steps"),
                limits.get("max_steps"),
            ),
            "seed": int(self.seed) if self.seed is not None else -1,
        }
        negative_prompt = str(self.negative_prompt or "").strip()
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return payload

    def generate_image(self) -> Data:
        """Return the image as a ``Data`` whose ``text`` is the image URL (also under ``image_url``)."""
        try:
            job = run_job(
                "/images/generations", self.build_payload(), api_key=self.api_key, max_wait_seconds=self.max_wait
            )
        except DeapiAPIError as exc:
            payload = error_payload(str(exc))
        else:
            payload = job_payload(job, kind="image", url_key="image_url")
        self.status = payload["text"]
        return Data(data=payload)
