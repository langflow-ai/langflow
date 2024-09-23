from tenacity import retry, stop_after_attempt, wait_fixed
from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint

# TODO: langchain_community.llms.huggingface_endpoint is depreciated. Need to update to langchain_huggingface, but have dependency with langchain_core 0.3.0
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import DictInput, DropdownInput, SecretStrInput, StrInput, IntInput, FloatInput
from typing import Any, Dict, Optional


class HuggingFaceEndpointsComponent(LCModelComponent):
    display_name: str = "HuggingFace"
    description: str = "Generate text using Hugging Face Inference APIs."
    icon = "HuggingFace"
    name = "HuggingFaceModel"

    inputs = LCModelComponent._base_inputs + [
        StrInput(
            name="model_id",
            display_name="Model ID",
            value="openai-community/gpt2",
        ),
        StrInput(
            name="inference_endpoint",
            display_name="Inference Endpoint",
            value="https://api-inference.huggingface.co/models/",
            info="Custom inference endpoint URL.",
        ),
        DropdownInput(
            name="task",
            display_name="Task",
            options=["text2text-generation", "text-generation", "summarization", "translation"],
            advanced=True,
            info="The task to call the model with. Should be a task that returns `generated_text` or `summary_text`.",
        ),
        SecretStrInput(name="huggingfacehub_api_token", display_name="API Token", password=True),
        DictInput(name="model_kwargs", display_name="Model Keyword Arguments", advanced=True),
        IntInput(name="retry_attempts", display_name="Retry Attempts", value=1, advanced=True),
        IntInput(
            name="max_new_tokens", display_name="Max New Tokens", value=512, info="Maximum number of generated tokens"
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            advanced=True,
            info="The number of highest probability vocabulary tokens to keep for top-k-filtering",
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            value=0.95,
            advanced=True,
            info="If set to < 1, only the smallest set of most probable tokens with probabilities that add up to `top_p` or higher are kept for generation",
        ),
        FloatInput(
            name="typical_p",
            display_name="Typical P",
            value=0.95,
            advanced=True,
            info="Typical Decoding mass.",
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            value=0.8,
            advanced=True,
            info="The value used to module the logits distribution",
        ),
        FloatInput(
            name="repetition_penalty",
            display_name="Repetition Penalty",
            advanced=True,
            info="The parameter for repetition penalty. 1.0 means no penalty.",
        ),
    ]

    def get_api_url(self) -> str:
        if "huggingface" in self.inference_endpoint.lower():
            return f"{self.inference_endpoint}{self.model_id}"
        else:
            return self.inference_endpoint

    def create_huggingface_endpoint(
        self,
        model_id: str,
        task: Optional[str],
        huggingfacehub_api_token: Optional[str],
        model_kwargs: Dict[str, Any],
        max_new_tokens: int,
        top_k: Optional[int],
        top_p: float,
        typical_p: Optional[float],
        temperature: Optional[float],
        repetition_penalty: Optional[float],
    ) -> HuggingFaceEndpoint:
        retry_attempts = self.retry_attempts
        endpoint_url = self.get_api_url()

        @retry(stop=stop_after_attempt(retry_attempts), wait=wait_fixed(2))
        def _attempt_create():
            return HuggingFaceEndpoint(
                endpoint_url=endpoint_url,
                task=task,
                huggingfacehub_api_token=huggingfacehub_api_token,
                model_kwargs=model_kwargs,
                max_new_tokens=max_new_tokens,
                top_k=top_k,
                top_p=top_p,
                typical_p=self.typical_p,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
            )

        return _attempt_create()

    def build_model(self) -> LanguageModel:
        model_id = self.model_id
        task = self.task or None
        huggingfacehub_api_token = self.huggingfacehub_api_token
        model_kwargs = self.model_kwargs or {}
        max_new_tokens = self.max_new_tokens
        top_k = self.top_k or None
        top_p = self.top_p
        typical_p = self.typical_p or None
        temperature = self.temperature or 0.8
        repetition_penalty = self.repetition_penalty or None

        try:
            llm = self.create_huggingface_endpoint(
                model_id=model_id,
                task=task,
                huggingfacehub_api_token=huggingfacehub_api_token,
                model_kwargs=model_kwargs,
                max_new_tokens=max_new_tokens,
                top_k=top_k,
                top_p=top_p,
                typical_p=typical_p,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
            )
        except Exception as e:
            raise ValueError("Could not connect to HuggingFace Endpoints API.") from e

        return llm
