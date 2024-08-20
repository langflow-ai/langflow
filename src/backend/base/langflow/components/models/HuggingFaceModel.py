from tenacity import retry, stop_after_attempt, wait_fixed

from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import DictInput, DropdownInput, SecretStrInput, StrInput, IntInput


class HuggingFaceEndpointsComponent(LCModelComponent):
    display_name: str = "Hugging Face API"
    description: str = "Generate text using Hugging Face Inference APIs."
    icon = "HuggingFace"
    name = "HuggingFaceModel"

    inputs = LCModelComponent._base_inputs + [
        StrInput(name="endpoint_url", display_name="Endpoint URL", value="https://api-inference.huggingface.co/models/openai-community/gpt2"),
        DropdownInput(
            name="task",
            display_name="Task",
            options=["text2text-generation", "text-generation", "summarization", "translation"],
            value="text-generation",
        ),
        SecretStrInput(name="huggingfacehub_api_token", display_name="API Token", password=True),
        DictInput(name="model_kwargs", display_name="Model Keyword Arguments", advanced=True),
        IntInput(name="retry_attempts", display_name="Retry Attempts", value=1, advanced=True),
    ]

    def create_huggingface_endpoint(
        self, endpoint_url: str, task: str, huggingfacehub_api_token: str, model_kwargs: dict
    ) -> HuggingFaceEndpoint:
        retry_attempts = self.retry_attempts  # Access the retry attempts input

        @retry(stop=stop_after_attempt(retry_attempts), wait=wait_fixed(2))
        def _attempt_create():
            return HuggingFaceEndpoint(
                endpoint_url=endpoint_url,
                task=task,
                huggingfacehub_api_token=huggingfacehub_api_token,
                model_kwargs=model_kwargs,
            )

        return _attempt_create()

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        endpoint_url = self.endpoint_url
        task = self.task
        huggingfacehub_api_token = self.huggingfacehub_api_token
        model_kwargs = self.model_kwargs or {}

        try:
            llm = self.create_huggingface_endpoint(endpoint_url, task, huggingfacehub_api_token, model_kwargs)
        except Exception as e:
            raise ValueError("Could not connect to HuggingFace Endpoints API.") from e

        return llm  # Return the LLM directly without wrapping in ChatHuggingFace
