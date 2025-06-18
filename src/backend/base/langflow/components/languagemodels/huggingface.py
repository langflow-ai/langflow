from typing import Any

from langchain_huggingface import HuggingFaceEndpoint
from tenacity import retry, stop_after_attempt, wait_fixed

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import DictInput, DropdownInput, FloatInput, IntInput, SliderInput, StrInput, SecretStrInput

# TODO: langchain_community.llms.huggingface_endpoint is depreciated.
#  Need to update to langchain_huggingface, but have dependency with langchain_core 0.3.0

# Constants
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"


class HuggingFaceEndpointsComponent(LCModelComponent):
    display_name: str = "HuggingFace"
    description: str = "Generate text using Hugging Face Inference APIs."
    icon = "HuggingFace"
    name = "HuggingFaceModel"

    inputs = [
        *LCModelComponent._base_inputs,
        DropdownInput(
            name="model_id",
            display_name="Model ID",
            info="Select a model from HuggingFace Hub",
            options=[
                DEFAULT_MODEL,
                "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "mistralai/Mistral-7B-Instruct-v0.3",
                "meta-llama/Llama-3.1-8B-Instruct",
                "Qwen/Qwen2.5-Coder-32B-Instruct",
                "Qwen/QwQ-32B-Preview",
                "openai-community/gpt2",
                "custom",
            ],
            value=DEFAULT_MODEL,
            real_time_refresh=True,
        ),
        StrInput(
            name="custom_model",
            display_name="Custom Model ID",
            info="Enter a custom model ID from HuggingFace Hub",
            value="",
            show=False,
        ),
        StrInput(
            name="endpoint_url",
            display_name="Endpoint URL",
            value="https://api-inference.huggingface.co/models/",
            info="Custom inference endpoint URL. For local deployment, use http://localhost:8080",
            required=True,
        ),
        IntInput(
            name="max_new_tokens",
            display_name="Max New Tokens",
            value=512,
            info="Maximum number of generated tokens",
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            value=50,
            advanced=True,
            info="The number of highest probability vocabulary tokens to keep for top-k-filtering",
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            value=0.95,
            advanced=True,
            info=(
                "If set to < 1, only the smallest set of most probable tokens with "
                "probabilities that add up to `top_p` or higher are kept for generation"
            ),
        ),
        FloatInput(
            name="typical_p",
            display_name="Typical P",
            value=0.95,
            advanced=True,
            info=(
                "Typical Decoding mass. If set to < 1, only the most typical tokens with "
                "probabilities that add up to typical_p or higher are kept for generation."
            ),
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.8,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            info=(
                "The value used to module the logits distribution. Higher values make the "
                "output more random, lower values make it more deterministic."
            ),
            advanced=True,
        ),
        FloatInput(
            name="repetition_penalty",
            display_name="Repetition Penalty",
            value=1.0,
            advanced=True,
            info="The parameter for repetition penalty. 1.0 means no penalty. Higher values reduce repetition.",
        ),
        DropdownInput(
            name="task",
            display_name="Task",
            options=["text2text-generation", "text-generation", "summarization", "translation"],
            value="text-generation",
            advanced=True,
            info="The task to call the model with. Should be a task that returns `generated_text` or `summary_text`.",
        ),
        SecretStrInput(
            name="huggingfacehub_api_token",
            display_name="HuggingFace API Token",
            info="Your HuggingFace API token. Not required for local deployments.",
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Keyword Arguments",
            advanced=True,
            info="Additional model-specific parameters to pass to the model.",
        ),
        IntInput(
            name="retry_attempts",
            display_name="Retry Attempts",
            value=3,
            advanced=True,
            info="Number of times to retry the API call if it fails.",
        ),
    ]

    def get_api_url(self) -> str:
        # If the endpoint is custom (does not contain 'huggingface'),
        # return the custom URL directly. This is used for local or private deployments.
        if "huggingface" not in self.inference_endpoint.lower():
            return self.inference_endpoint
        # If using the standard HuggingFace API, return only the model_id or custom_model.
        # The HuggingFaceEndpoint library will construct the full URL internally.
        if self.model_id == "custom":
            if not self.custom_model:
                raise ValueError("Custom model ID is required when 'custom' is selected")
            return self.custom_model
        return self.model_id

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update build configuration based on field updates."""
        try:
            if field_name is None or field_name == "model_id":
                # If model_id is custom, show custom model field
                if field_value == "custom":
                    build_config["custom_model"]["show"] = True
                    build_config["custom_model"]["required"] = True
                else:
                    build_config["custom_model"]["show"] = False
                    build_config["custom_model"]["value"] = ""

        except (KeyError, AttributeError) as e:
            self.log(f"Error updating build config: {e!s}")
        return build_config
    
    def _get_model_param(self):
        """Restituisce il parametro corretto da passare a HuggingFaceEndpoint: model, endpoint_url o repo_id."""
        # Se endpoint_url è custom (non contiene 'huggingface'), usalo come endpoint_url
        if "huggingface" not in self.endpoint_url.lower():
            return {"endpoint_url": self.endpoint_url}
        # Se model_id è custom, usa custom_model come repo_id
        if self.model_id == "custom":
            if not self.custom_model:
                raise ValueError("Custom model ID is required when 'custom' is selected")
            return {"repo_id": self.custom_model}
        # Altrimenti usa model_id come repo_id
        return {"repo_id": self.model_id}

    def create_huggingface_endpoint(
        self,
        task: str | None,
        huggingfacehub_api_token: str | None,
        model_kwargs: dict[str, Any],
        max_new_tokens: int,
        top_k: int | None,
        top_p: float,
        typical_p: float | None,
        temperature: float | None,
        repetition_penalty: float | None,
    ) -> HuggingFaceEndpoint:
        """Crea un'istanza di HuggingFaceEndpoint seguendo la signature della reference."""
        retry_attempts = self.retry_attempts
        model_param = self._get_model_param()

        @retry(stop=stop_after_attempt(retry_attempts), wait=wait_fixed(2))
        def _attempt_create():
            return HuggingFaceEndpoint(
                **model_param,
                task=task,
                model_kwargs=model_kwargs,
                max_new_tokens=max_new_tokens,
                huggingfacehub_api_token=huggingfacehub_api_token,
                top_k=top_k,
                top_p=top_p,
                typical_p=typical_p,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
            )

        return _attempt_create()

    def build_model(self) -> LanguageModel:
        """Build and return the HuggingFaceEndpoint model."""
        task = self.task or None
        model_kwargs = self.model_kwargs or {}
        max_new_tokens = self.max_new_tokens
        top_k = self.top_k
        top_p = self.top_p
        typical_p = self.typical_p
        temperature = self.temperature
        repetition_penalty = self.repetition_penalty

        try:
            llm = self.create_huggingface_endpoint(
                task=task,
                huggingfacehub_api_token=self.huggingfacehub_api_token,
                model_kwargs=model_kwargs,
                max_new_tokens=max_new_tokens,
                top_k=top_k,
                top_p=top_p,
                typical_p=typical_p,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
            )
        except Exception as e:
            msg = f"Could not connect to HuggingFace Endpoints API: {e!s}"
            raise ValueError(msg) from e

        return llm
