"""ModelsLab Image Generation component for Langflow.

Generates images using ModelsLab's text-to-image API (Flux, SDXL,
Playground v2.5, and 1000+ community models). Handles both synchronous
and asynchronous (polling) responses automatically.

Get your API key at: https://modelslab.com
API docs: https://docs.modelslab.com/image-generation/text-to-image
"""

import time
from typing import Any

import requests
from langflow.custom import Component
from langflow.io import (
    DropdownInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    SliderInput,
)
from langflow.schema import Data

MODELSLAB_IMAGE_API = "https://modelslab.com/api/v6/images/text2img"
MODELSLAB_FETCH_API = "https://modelslab.com/api/v6/fetch/{task_id}"

MODELSLAB_IMAGE_MODELS = [
    "flux",
    "flux-schnell",
    "stable-diffusion-xl-base-1.0",
    "playground-v2.5-1024px-aesthetic",
    "dreamshaper-8",
    "realistic-vision-v5",
    "juggernautXL-v9",
    "deliberate-v3",
    "revAnimated-v2",
    "dreamlike-photoreal-2.0",
]


class ModelsLabImageComponent(Component):
    """ModelsLab Image Generation component for Langflow.

    Generates images via ModelsLab's API and returns the image URL(s)
    as Langflow Data objects compatible with downstream components.
    """

    display_name: str = "ModelsLab Image Generation"
    description: str = (
        "Generate images using ModelsLab's API. Supports Flux, SDXL, "
        "Playground v2.5, and 1000+ community models. Returns image URL(s)."
    )
    documentation: str = "https://docs.modelslab.com/image-generation/text-to-image"
    icon: str = "Image"
    name: str = "ModelsLabImage"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="ModelsLab API Key",
            info="Your ModelsLab API key. Get one at https://modelslab.com",
            required=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="Text description of the image to generate.",
            required=True,
        ),
        MessageTextInput(
            name="negative_prompt",
            display_name="Negative Prompt",
            info="What to exclude from the image.",
            value="low quality, blurry, deformed, ugly, watermark",
            advanced=True,
        ),
        DropdownInput(
            name="model_id",
            display_name="Model",
            info="Image generation model to use.",
            options=MODELSLAB_IMAGE_MODELS,
            value="flux",
        ),
        IntInput(
            name="width",
            display_name="Width",
            info="Image width in pixels.",
            value=1024,
            advanced=True,
        ),
        IntInput(
            name="height",
            display_name="Height",
            info="Image height in pixels.",
            value=1024,
            advanced=True,
        ),
        IntInput(
            name="num_inference_steps",
            display_name="Steps",
            info="Number of denoising steps. More steps = better quality but slower.",
            value=20,
            advanced=True,
        ),
        SliderInput(
            name="guidance_scale",
            display_name="Guidance Scale (CFG)",
            info="How closely to follow the prompt. Higher = more literal.",
            value=7.5,
            range_spec={"min": 1.0, "max": 20.0, "step": 0.5},
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="Random seed for reproducibility. Use -1 for random.",
            value=-1,
            advanced=True,
        ),
        IntInput(
            name="samples",
            display_name="Number of Images",
            info="How many images to generate.",
            value=1,
            advanced=True,
        ),
        IntInput(
            name="poll_timeout",
            display_name="Timeout (seconds)",
            info="Maximum seconds to wait for async generation jobs.",
            value=180,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Image URL(s)",
            name="image_urls",
            method="generate_image",
        ),
    ]

    def generate_image(self) -> Data:
        """Call ModelsLab image API and return image URL(s) as a Data object."""
        if not self.api_key:
            msg = "ModelsLab API key is required."
            raise ValueError(msg)

        if not self.prompt:
            msg = "Prompt is required."
            raise ValueError(msg)

        payload: dict[str, Any] = {
            "key": self.api_key,
            "model_id": self.model_id,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt or "",
            "width": str(self.width),
            "height": str(self.height),
            "samples": str(self.samples),
            "num_inference_steps": self.num_inference_steps,
            "guidance_scale": self.guidance_scale,
            "safety_checker": "no",
            "enhance_prompt": "yes",
        }

        if self.seed and self.seed != -1:
            payload["seed"] = self.seed

        try:
            response = requests.post(
                MODELSLAB_IMAGE_API,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as e:
            msg = f"ModelsLab API request failed: {e}"
            raise RuntimeError(msg) from e

        # Handle failure immediately
        if result.get("status") == "failed":
            msg = f"ModelsLab generation failed: {result.get('message', 'unknown error')}"
            raise RuntimeError(msg)

        # Async path — poll until done
        if result.get("status") == "processing":
            task_id = result.get("id")
            if not task_id:
                msg = "ModelsLab returned processing status but no task ID"
                raise RuntimeError(msg)
            result = self._poll_until_done(task_id)

        # Extract image URLs
        image_urls: list[str] = []
        if isinstance(result.get("output"), list):
            image_urls = result["output"]
        elif result.get("output"):
            image_urls = [result["output"]]
        elif result.get("url"):
            image_urls = [result["url"]]

        if not image_urls:
            msg = "ModelsLab returned no image URLs"
            raise RuntimeError(msg)

        self.status = f"Generated {len(image_urls)} image(s)"

        return Data(
            data={
                "image_urls": image_urls,
                "model": self.model_id,
                "prompt": self.prompt,
            },
            text=image_urls[0],
        )

    def _poll_until_done(self, task_id: str) -> dict:
        """Poll ModelsLab fetch endpoint until the task completes."""
        deadline = time.time() + self.poll_timeout
        poll_interval = 3.0

        while time.time() < deadline:
            time.sleep(poll_interval)

            try:
                resp = requests.post(
                    MODELSLAB_FETCH_API.format(task_id=task_id),
                    json={"key": self.api_key},
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException:
                # Transient network error — keep polling
                continue

            if data.get("status") == "success":
                return data
            if data.get("status") == "failed":
                msg = f"ModelsLab task failed: {data.get('message', 'unknown')}"
                raise RuntimeError(msg)

            # Still processing — back off slightly
            poll_interval = min(poll_interval * 1.2, 10.0)

        msg = f"ModelsLab image generation timed out after {self.poll_timeout}s (task: {task_id})"
        raise TimeoutError(msg)
