import requests
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.schema.data import Data
from pydantic.v1 import SecretStr

EMPIRIOLABS_BASE_URL = "https://api.empiriolabs.ai/v1"

# EmpirioLabs image generation models (category=image). These use the OpenAI
# Images request shape at POST /v1/images/generations.
EMPIRIOLABS_IMAGE_MODELS = [
    "seedream-5-0-lite",
    "qwen-image-2-0",
    "flux-2-klein-4b",
    "amazon-nova-canvas",
    "hunyuan-image-3",
    "wan2-7-image",
    "janus-pro-deepseek",
]

# Allowed aspect ratios mirror the common set supported across the image models.
ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9", "9:21"]


class EmpirioLabsImageGenerationComponent(Component):
    display_name = "EmpirioLabs AI Image Generation"
    description = "Generate an image from a text prompt using EmpirioLabs AI image models such as Seedream, \
        Qwen-Image, FLUX, Nova Canvas, and HunyuanImage."
    documentation = "https://docs.empiriolabs.ai"
    icon = "EmpirioLabs"
    name = "EmpirioLabsImageGeneration"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="EmpirioLabs API Key",
            info="The EmpirioLabs API Key to use for EmpirioLabs AI image models.",
            required=True,
            value="EMPIRIOLABS_API_KEY",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="The text prompt to generate the image from.",
            required=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The EmpirioLabs image model to use for generation.",
            options=EMPIRIOLABS_IMAGE_MODELS,
            value=EMPIRIOLABS_IMAGE_MODELS[0],
            refresh_button=True,
            required=True,
        ),
        DropdownInput(
            name="aspect_ratio",
            display_name="Aspect Ratio",
            info="The aspect ratio of the generated image. Used when the selected model supports it.",
            options=ASPECT_RATIOS,
            value="1:1",
            required=False,
        ),
        MessageTextInput(
            name="size",
            display_name="Size",
            info="Optional explicit pixel size such as '1024x1024'. Takes priority over aspect ratio "
            "when the selected model supports an explicit size.",
            required=False,
            advanced=True,
        ),
        IntInput(
            name="n",
            display_name="Number of Images",
            info="The number of images to generate.",
            value=1,
            required=False,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="Makes generation deterministic. Using the same seed and parameters produces "
            "the same image each time. Used when the selected model supports it.",
            required=False,
            tool_mode=True,
            advanced=True,
        ),
        MessageTextInput(
            name="negative_prompt",
            display_name="Negative Prompt",
            info="The text prompt describing what to avoid in the generated image. "
            "Used when the selected model supports it.",
            required=False,
            tool_mode=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Image Generation Results", name="image_generation_results", method="generate_image"),
    ]

    def _get_token(self) -> str:
        api_key = getattr(self, "api_key", None)
        if not api_key:
            return ""
        return SecretStr(api_key).get_secret_value() if isinstance(api_key, str) else api_key

    def get_models(self) -> list[str]:
        """Fetch the live list of image models from the EmpirioLabs API, falling back to the static list."""
        url = f"{EMPIRIOLABS_BASE_URL}/models"
        headers = {"Content-Type": "application/json"}
        token = self._get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            image_models = [
                model["id"]
                for model in model_list.get("data", [])
                if model.get("category") == "image"
                or (isinstance(model.get("metadata"), dict) and model["metadata"].get("category") == "image")
            ]
        except requests.RequestException as e:
            self.status = f"Error fetching models: {e}"
            return EMPIRIOLABS_IMAGE_MODELS
        return image_models or EMPIRIOLABS_IMAGE_MODELS

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):  # noqa: ARG002
        if field_name in {"api_key", "model_name"}:
            build_config["model_name"]["options"] = self.get_models()
        return build_config

    def generate_image(self) -> Data:
        token = self._get_token()
        if not token:
            missing_key_error = "An EmpirioLabs API key is required to generate images."
            raise ValueError(missing_key_error)

        if not self.prompt or not self.prompt.strip():
            invalid_prompt_error = "A non-empty prompt is required to generate an image."
            raise ValueError(invalid_prompt_error)

        # Build the OpenAI Images request body. sync: true makes the API hold the
        # request and return the finished image instead of an async job envelope.
        payload: dict = {
            "model": self.model_name,
            "prompt": self.prompt.strip(),
            "sync": True,
        }
        if self.size and self.size.strip():
            payload["size"] = self.size.strip()
        elif self.aspect_ratio:
            payload["aspect_ratio"] = self.aspect_ratio
        if self.n:
            payload["n"] = self.n
        if self.seed:
            payload["seed"] = self.seed
        if self.negative_prompt and self.negative_prompt.strip():
            payload["negative_prompt"] = self.negative_prompt.strip()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{EMPIRIOLABS_BASE_URL}/images/generations",
                headers=headers,
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)

        items = result.get("data") if isinstance(result, dict) else None
        if not items:
            failed_response_error = "EmpirioLabs API did not return any generated image."
            raise ValueError(failed_response_error)

        image_urls = [item.get("url") for item in items if isinstance(item, dict) and item.get("url")]
        first = items[0] if isinstance(items[0], dict) else {}
        image_url = first.get("url")
        image_b64 = first.get("b64_json")

        data_payload: dict = dict(result)
        if image_url:
            data_payload["image_url"] = image_url
            self.status = image_url
        elif image_b64:
            data_payload["b64_json"] = image_b64
            self.status = "Generated image returned as base64 content."
        if image_urls:
            data_payload["image_urls"] = image_urls

        return Data(data=data_payload)
