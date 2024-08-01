from langchain_community.chat_models.huggingface import ChatHuggingFace
from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import DictInput, DropdownInput, SecretStrInput, StrInput


class HuggingFaceEndpointsComponent(LCModelComponent):
    display_name: str = "Hugging Face API"
    description: str = "Generate text using Hugging Face Inference APIs."
    icon = "HuggingFace"
    name = "HuggingFaceModel"

    inputs = LCModelComponent._base_inputs + [
        SecretStrInput(name="endpoint_url", display_name="Endpoint URL", password=True),
        StrInput(
            name="model_id",
            display_name="Model Id",
            info="Id field of endpoint_url response.",
        ),
        DropdownInput(
            name="task",
            display_name="Task",
            options=["text2text-generation", "text-generation", "summarization"],
        ),
        SecretStrInput(name="huggingfacehub_api_token", display_name="API token", password=True),
        DictInput(name="model_kwargs", display_name="Model Keyword Arguments", advanced=True),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        endpoint_url = self.endpoint_url
        task = self.task
        huggingfacehub_api_token = self.huggingfacehub_api_token
        model_kwargs = self.model_kwargs or {}

        try:
            llm = HuggingFaceEndpoint(  # type: ignore
                endpoint_url=endpoint_url,
                task=task,
                huggingfacehub_api_token=huggingfacehub_api_token,
                model_kwargs=model_kwargs,
            )
        except Exception as e:
            raise ValueError("Could not connect to HuggingFace Endpoints API.") from e

        output = ChatHuggingFace(llm=llm, model_id=self.model_id)
        return output  # type: ignore
