from typing import Any

from langchain_huggingface import HuggingFaceEndpoint
from tenacity import retry, stop_after_attempt, wait_fixed

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import DictInput, DropdownInput, FloatInput, IntInput, SliderInput, StrInput

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
        StrInput(
            name="inference_endpoint",
            display_name="Inference Endpoint",
            value="https://api-inference.huggingface.co/models/",
            info="Custom inference endpoint URL. For local deployment, use http://localhost:8080",
            required=True,
        ),
        StrInput(
            name="model_name",
            display_name="Model Name",
            info="The name of the model to use (e.g., 'mistralai/Mixtral-8x7B-Instruct-v0.1')",
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
        """Get the full API URL for the model."""
        endpoint = self.inference_endpoint.rstrip("/")
        model_name = self.model_name.strip()
        return f"{endpoint}/{model_name}"

    def create_huggingface_endpoint(
        self,
        task: str | None,
        model_kwargs: dict[str, Any],
        max_new_tokens: int,
        top_k: int | None,
        top_p: float,
        typical_p: float | None,
        temperature: float | None,
        repetition_penalty: float | None,
    ) -> HuggingFaceEndpoint:
        """Create a HuggingFaceEndpoint instance with retry logic."""
        retry_attempts = self.retry_attempts
        endpoint_url = self.get_api_url()

        # Prepare model kwargs
        model_kwargs = model_kwargs or {}
        if top_k is not None:
            model_kwargs["top_k"] = top_k
        if top_p is not None:
            model_kwargs["top_p"] = top_p
        if typical_p is not None:
            model_kwargs["typical_p"] = typical_p
        if temperature is not None:
            model_kwargs["temperature"] = temperature
        if repetition_penalty is not None:
            model_kwargs["repetition_penalty"] = repetition_penalty

        @retry(stop=stop_after_attempt(retry_attempts), wait=wait_fixed(2))
        def _attempt_create():
            return HuggingFaceEndpoint(
                endpoint_url=endpoint_url,
                task=task,
                model_kwargs=model_kwargs,
                max_new_tokens=max_new_tokens,
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
