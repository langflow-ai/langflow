from typing import Any

from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint
from tenacity import retry, stop_after_attempt, wait_fixed

# TODO: langchain_community.llms.huggingface_endpoint is depreciated.
#  Need to update to langchain_huggingface, but have dependency with langchain_core 0.3.0
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs.inputs import HandleInput
from langflow.io import DictInput, DropdownInput, IntInput, SecretStrInput, StrInput


class HuggingFaceEndpointsComponent(LCModelComponent):
    display_name: str = "HuggingFace"
    description: str = "Generate text using Hugging Face Inference APIs."
    icon = "HuggingFace"
    name = "HuggingFaceModel"

    inputs = [
        *LCModelComponent._base_inputs,
        StrInput(name="model_id", display_name="Model ID", value="openai-community/gpt2"),
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
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def get_api_url(self) -> str:
        if "huggingface" in self.inference_endpoint.lower():
            return f"{self.inference_endpoint}{self.model_id}"
        return self.inference_endpoint

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
                typical_p=typical_p,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
            )

        return _attempt_create()

    def build_model(self) -> LanguageModel:
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
            msg = "Could not connect to HuggingFace Endpoints API."
            raise ValueError(msg) from e

        return llm
