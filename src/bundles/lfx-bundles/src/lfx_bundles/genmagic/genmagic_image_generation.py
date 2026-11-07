"""Generate an image with GenMagic."""

from __future__ import annotations

import re
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.message import Message

from lfx_bundles.genmagic.genmagic_common import (
    API_KEY_INFO,
    API_KEY_VARIABLE,
    AUTO_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    GenMagicAPIError,
    call_api,
    chosen_model,
    metering,
    positive_seconds,
    refresh_model_dropdown,
    response_json,
    text_value,
)

IMAGE_SIZES = ["1024x1024", "1792x1024", "1024x1792"]


class GenMagicImageGenerationComponent(Component):
    """Generate an image from a prompt, or transform a reference image, and return its hosted URL."""

    display_name = "GenMagic Image Generation"
    description = "Generate an image from a text prompt, or transform a reference image, with any GenMagic image model."
    documentation = DOCUMENTATION_URL
    icon = "GenMagic"
    name = "GenMagicImageGeneration"

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
            info="Describe the image, or the change to make when a reference image is set.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info=f"The image model. {AUTO_MODEL} lets GenMagic pick its recommended model. "
            "The list loads from the live GenMagic catalog; type a model ID to use one that is not listed.",
            options=[],
            value=AUTO_MODEL,
            combobox=True,
            refresh_button=True,
        ),
        DropdownInput(
            name="size",
            display_name="Size",
            info="The size of the generated image in pixels.",
            options=IMAGE_SIZES,
            value=IMAGE_SIZES[0],
        ),
        MessageTextInput(
            name="reference_image",
            display_name="Reference Image URL",
            info="Optional. An https URL or a data:image URL of a picture to transform (image-to-image). "
            "GenMagic fetches it, so it must be reachable from the internet.",
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for GenMagic to answer.",
            value=int(DEFAULT_TIMEOUT_SECONDS),
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Image", name="image", method="build_image", tool_mode=False),
        Output(display_name="Image URL", name="image_url", method="build_image_url", tool_mode=False),
        Output(display_name="Result", name="result", method="build_result"),
    ]

    def _pre_run_setup(self) -> None:
        """Forget the previous build's image, so this build makes one paid request shared by its outputs."""
        # One paid request per build, shared by every output that is connected.
        self._generation = None

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Load the image models from the live GenMagic catalog (a public endpoint that needs no key)."""
        if field_name not in {None, "model_name"}:
            return build_config
        return refresh_model_dropdown(build_config, "model_name", "image", include_auto=True)

    def _request_body(self) -> dict[str, Any]:
        """The JSON body for POST /images/generations, built from the component's inputs."""
        prompt = text_value(self.prompt)
        if not prompt:
            msg = "Enter a prompt for the image."
            raise GenMagicAPIError(msg)
        body: dict[str, Any] = {"prompt": prompt, "size": text_value(self.size) or IMAGE_SIZES[0]}
        body["response_format"] = "url"
        if model := chosen_model(self.model_name):
            body["model"] = model
        if reference := text_value(self.reference_image):
            body["image"] = reference
        return body

    def generate(self) -> dict[str, Any]:
        """Run the request once and return the image ``url`` with its model, prompt and cost."""
        body = self._request_body()
        cached = self._generation
        if cached is not None and cached[0] == body:
            return cached[1]
        response = call_api(
            "POST",
            "/images/generations",
            api_key=self.api_key,
            timeout=positive_seconds(self.timeout, DEFAULT_TIMEOUT_SECONDS),
            json=body,
        )
        payload = response_json(response)
        items = payload.get("data")
        first = items[0] if isinstance(items, list) and items and isinstance(items[0], dict) else {}
        url = str(first.get("url") or "").strip()
        if not url:
            msg = "GenMagic returned no image."
            raise GenMagicAPIError(msg, status=response.status_code)
        result: dict[str, Any] = {
            "url": url,
            "model": first.get("model") or payload.get("model") or body.get("model") or AUTO_MODEL,
            "prompt": body["prompt"],
            "size": body["size"],
            **metering(response),
        }
        if revised := first.get("revised_prompt"):
            result["revised_prompt"] = revised
        self._generation = (body, result)
        self.status = url
        return result

    def build_image(self) -> Message:
        """The image as a Markdown picture, so Chat Output shows it inline."""
        result = self.generate()
        alt = re.sub(r"[\[\]\r\n]+", " ", result["prompt"]).strip()[:100]
        return Message(text=f"![{alt}]({result['url']})")

    def build_image_url(self) -> Message:
        """The hosted URL of the image, to wire into another component."""
        return Message(text=self.generate()["url"])

    def build_result(self) -> Data:
        """The URL, model, prompt, size and what the call cost."""
        return Data(data=self.generate())
