import time

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data

_MODELSLAB_TEXT2IMG_URL = "https://modelslab.com/api/v6/images/text2img"
_MODELSLAB_FETCH_URL = "https://modelslab.com/api/v6/images/fetch/{request_id}"
_POLL_INTERVAL = 5  # seconds
_POLL_TIMEOUT = 300  # seconds


class ModelsLabImageGenerationComponent(Component):
    display_name = "Image Generation"
    description = (
        "Generate images using the ModelsLab API. Supports Flux, SDXL, Stable Diffusion 3.5, and 100+ community models."
    )
    documentation = "https://docs.modelslab.com"
    icon = "ModelsLab"
    name = "ModelsLabImageGeneration"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="ModelsLab API Key",
            info="Your ModelsLab API key. Get yours at https://modelslab.com/account/api-key",
            required=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="Text prompt describing the image to generate.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_id",
            display_name="Model",
            info="ModelsLab model to use for image generation.",
            options=["flux", "fluxpro", "sdxl", "sd3.5", "realistic-vision-v6", "juggernautxl-v10"],
            value="flux",
            required=False,
        ),
        DropdownInput(
            name="size",
            display_name="Image Size",
            info="Dimensions of the generated image (width x height).",
            options=["512x512", "1024x1024", "1344x768", "768x1344", "1536x640"],
            value="1024x1024",
            required=False,
        ),
        MessageTextInput(
            name="negative_prompt",
            display_name="Negative Prompt",
            info="What to exclude from the generated image.",
            value="blurry, low quality, watermark, distorted",
            required=False,
            tool_mode=True,
            advanced=True,
        ),
        IntInput(
            name="num_inference_steps",
            display_name="Steps",
            info="Number of denoising steps (10-50). Higher values produce better quality but take longer.",
            value=30,
            required=False,
            advanced=True,
        ),
        IntInput(
            name="samples",
            display_name="Number of Images",
            info="Number of images to generate (1-4).",
            value=1,
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Image Generation Result",
            name="image_generation_result",
            method="generate_image",
        ),
    ]

    def generate_image(self) -> Data:
        """Generate an image using the ModelsLab API.

        ModelsLab uses key-in-body authentication and an asynchronous pattern:
        responses may return ``status: processing`` with a request_id, requiring
        polling until ``status: success``.
        """
        dims = self.size.split("x") if self.size else ["1024", "1024"]
        width = int(dims[0]) if len(dims) == 2 else 1024
        height = int(dims[1]) if len(dims) == 2 else 1024

        payload = {
            "key": self.api_key,
            "model_id": self.model_id or "flux",
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt or "blurry, low quality, watermark, distorted",
            "width": width,
            "height": height,
            "samples": max(1, min(4, self.samples or 1)),
            "num_inference_steps": max(10, min(50, self.num_inference_steps or 30)),
            "safety_checker": "no",
            "enhance_prompt": "yes",
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    _MODELSLAB_TEXT2IMG_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            self.status = f"HTTP error: {e}"
            return Data(data={"error": str(e), "success": False})

        if data.get("status") == "error":
            msg = data.get("message", "Unknown ModelsLab error")
            self.status = f"Error: {msg}"
            return Data(data={"error": msg, "success": False})

        if data.get("status") == "processing":
            request_id = str(data.get("id", ""))
            if not request_id:
                self.status = "Error: processing status with no request_id"
                return Data(data={"error": "No request_id in processing response", "success": False})
            data = self._poll_until_ready(request_id)
            if not data:
                return Data(data={"error": "Generation timed out", "success": False})

        output_urls = data.get("output", [])
        if not output_urls:
            self.status = "Error: no output URLs in response"
            return Data(data={"error": "No output URLs returned", "success": False})

        result = {
            "success": True,
            "urls": output_urls,
            "url": output_urls[0],
            "model_id": self.model_id,
            "prompt": self.prompt,
        }
        self.status = f"Generated {len(output_urls)} image(s)"
        return Data(data=result)

    def _poll_until_ready(self, request_id: str) -> dict:
        """Poll ModelsLab fetch endpoint synchronously until image is ready."""
        fetch_url = _MODELSLAB_FETCH_URL.format(request_id=request_id)
        fetch_payload = {"key": self.api_key}
        deadline = time.time() + _POLL_TIMEOUT

        with httpx.Client(timeout=30.0) as client:
            while time.time() < deadline:
                time.sleep(_POLL_INTERVAL)
                try:
                    resp = client.post(
                        fetch_url,
                        json=fetch_payload,
                        headers={"Content-Type": "application/json"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPError:
                    continue

                if data.get("status") == "error":
                    self.status = f"Error: {data.get('message', 'Generation failed')}"
                    return {}
                if data.get("status") == "success":
                    return data

        self.status = f"Error: timed out after {_POLL_TIMEOUT}s"
        return {}
