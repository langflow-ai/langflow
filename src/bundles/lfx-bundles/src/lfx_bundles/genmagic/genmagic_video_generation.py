"""Generate a video with GenMagic and wait for it to render."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

from lfx_bundles.genmagic.genmagic_common import (
    API_KEY_INFO,
    API_KEY_VARIABLE,
    AUTO_MODEL,
    DOCUMENTATION_URL,
    VIDEO_REQUEST_TIMEOUT_SECONDS,
    GenMagicAPIError,
    call_api,
    chosen_model,
    optional_positive_int,
    positive_seconds,
    refresh_model_dropdown,
    response_json,
    text_value,
    video_result,
    wait_for_video,
)

ASPECT_RATIOS = ["16:9", "9:16", "1:1"]
DEFAULT_WAIT_SECONDS = 600
DEFAULT_POLL_SECONDS = 5.0


def makes_video_from_prompt(model: dict[str, Any]) -> bool:
    """Whether a catalog entry can make a clip from a text prompt (editors and upscalers cannot)."""
    capabilities = model.get("capabilities")
    return not (isinstance(capabilities, dict) and capabilities.get("text_to_video") is False)


class GenMagicVideoGenerationComponent(Component):
    """Start a GenMagic video job, poll it until it finishes or the timeout passes, and return the clip URL."""

    display_name = "GenMagic Video Generation"
    description = (
        "Generate a video from a text prompt (or an opening image) with any GenMagic video model, "
        "and wait for the render to finish."
    )
    documentation = DOCUMENTATION_URL
    icon = "GenMagic"
    name = "GenMagicVideoGeneration"

    # The request and result of this build, shared by every connected output (see _pre_run_setup).
    _generation: tuple[dict[str, Any], dict[str, Any]] | None = None

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="GenMagic API Key",
            info=API_KEY_INFO,
            value=API_KEY_VARIABLE,
            required=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="Describe the video. With a Start Image, describe the motion.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info=f"The video model. {AUTO_MODEL} lets GenMagic pick its recommended text-to-video model. "
            "The list loads from the live GenMagic catalog; type a model ID to use one that is not listed.",
            options=[],
            value=AUTO_MODEL,
            combobox=True,
            refresh_button=True,
        ),
        DropdownInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            info="The shape of the clip.",
            options=ASPECT_RATIOS,
            value=ASPECT_RATIOS[0],
        ),
        IntInput(
            name="duration",
            display_name="Duration (seconds)",
            info="Clip length. Leave at 0 for the model's default (usually 5). Each model accepts only certain "
            "lengths, and the price scales with the length.",
            value=0,
        ),
        MessageTextInput(
            name="start_image",
            display_name="Start Image URL",
            info="Optional. An https URL or a data:image URL the clip opens on (image-to-video). "
            "Only models that accept a first frame can use it.",
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for the render. A video is billed only when it completes. If the timeout passes, "
            "the error names the job ID, and the GenMagic Video Status component can fetch the clip later.",
            value=DEFAULT_WAIT_SECONDS,
            advanced=True,
        ),
        FloatInput(
            name="poll_interval",
            display_name="Poll Interval (seconds)",
            info="How often to check on the render.",
            value=DEFAULT_POLL_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Video URL", name="video_url", method="build_video_url", tool_mode=False),
        Output(display_name="Result", name="result", method="build_result"),
    ]

    def _pre_run_setup(self) -> None:
        """Forget the previous build's job, so this build starts one paid job shared by its outputs."""
        # One paid job per build, shared by every output that is connected.
        self._generation = None

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Load the text-to-video models from the live GenMagic catalog (a public endpoint that needs no key)."""
        if field_name not in {None, "model_name"}:
            return build_config
        return refresh_model_dropdown(
            build_config, "model_name", "video", include_auto=True, keep=makes_video_from_prompt
        )

    def _request_body(self) -> dict[str, Any]:
        """The JSON body for POST /videos, built from the component's inputs."""
        prompt = text_value(self.prompt)
        if not prompt:
            msg = "Enter a prompt for the video."
            raise GenMagicAPIError(msg)
        body: dict[str, Any] = {"prompt": prompt, "aspect_ratio": text_value(self.aspect_ratio) or ASPECT_RATIOS[0]}
        if model := chosen_model(self.model_name):
            body["model"] = model
        if duration := optional_positive_int(self.duration):
            body["duration"] = duration
        if image := text_value(self.start_image):
            body["image"] = image
        return body

    def generate(self) -> dict[str, Any]:
        """Start the job, wait for it, and return the finished clip's ``url`` with its model and cost."""
        body = self._request_body()
        cached = self._generation
        if cached is not None and cached[0] == body:
            return cached[1]
        created = call_api("POST", "/videos", api_key=self.api_key, timeout=VIDEO_REQUEST_TIMEOUT_SECONDS, json=body)
        job, costs = wait_for_video(
            response_json(created),
            api_key=self.api_key,
            timeout=positive_seconds(self.timeout, DEFAULT_WAIT_SECONDS),
            poll_interval=positive_seconds(self.poll_interval, DEFAULT_POLL_SECONDS),
        )
        if job.get("status") == "failed":
            msg = f"GenMagic could not render the video (job {job.get('id')}): {job.get('error') or 'unknown error'}"
            raise GenMagicAPIError(msg, code="video_failed")
        if not job.get("url"):
            msg = f"GenMagic reported video job {job.get('id')} as completed but returned no URL."
            raise GenMagicAPIError(msg)
        result = {**video_result(job, costs), "prompt": body["prompt"], "aspect_ratio": body["aspect_ratio"]}
        self._generation = (body, result)
        self.status = result["url"]
        return result

    def build_video_url(self) -> Message:
        """The hosted URL of the finished clip, to wire into another component."""
        return Message(text=self.generate()["url"])

    def build_result(self) -> Data:
        """The URL, job ID, model, prompt, aspect ratio and what the video cost."""
        return Data(data=self.generate())
