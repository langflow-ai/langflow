from langchain_community.chat_models.huggingface import ChatHuggingFace
from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.io import BoolInput, DictInput, DropdownInput, MessageInput, SecretStrInput, StrInput
from langflow.schema.message import Message

from langflow.services.deps import get_storage_service
from langflow.services.storage.utils import build_content_type_from_extension

import requests
import json


class HuggingFaceEndpointsComponent(LCModelComponent):
    display_name: str = "Hugging Face API"
    description: str = "Generate text using Hugging Face Inference APIs."
    icon = "HuggingFace"
    name = "HuggingFaceModel"

    inputs = [
        MessageInput(name="input_value", display_name="Input"),
        SecretStrInput(name="endpoint_url", display_name="Endpoint URL", password=True),
        StrInput(
            name="model_id",
            display_name="Model Id",
            info="Id field of endpoint_url response.",
        ),
        DropdownInput(
            name="task",
            display_name="Task",
            options=["text2text-generation", "text-generation", "summarization", "image-classification"],
        ),
        SecretStrInput(name="huggingfacehub_api_token", display_name="API token", password=True),
        DictInput(name="model_kwargs", display_name="Model Keyword Arguments", advanced=True),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="text", name="text", method="output_to_text"),
        Output(display_name="language_model", name="language_model", method="build_model")
    ]

    async def query(self, filename):
        headers = {
            "Accept" : "application/json",
            "Authorization": f"Bearer {self.huggingfacehub_api_token}",
            "Content-Type": "image/jpeg" 
        }
        try:
            flow_id_str = filename.split("/")[0]
            file_name = filename.split("/")[-1]
            storage_service = get_storage_service()
            file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
            response = requests.post(self.endpoint_url, headers=headers, data=file_content)
            return response.json()
        except Exception as e:
            raise e
    
    async def image_classification(self) -> Message:
        response = await self.query(self.input_value.files[0])
        return Message(text=json.dumps(response))

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
    
    async def output_to_text(self) -> Message:
        if self.task == "image-classification":
            return await self.image_classification()
        
        # TODO: Implement other tasks e.g. text2text-generation, text-generation, summarization
