import asyncio
import json
import operator
from functools import reduce
from typing import Optional
import httpx
from langflow.custom.custom_component.component import Component

from langflow.schema.message import Message
from langflow.schema.data import Data
from langflow.template.field.base import Output
from loguru import logger
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.base.models.openai_constants import MODEL_NAMES
from langflow.field_typing import NestedDict, Text, LanguageModel
from langflow.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageInput,
    SecretStrInput,
    StrInput,
)
import requests



class AIMLModelComponent(Component):
    display_name = "AI/ML API"
    description = "Generates text using the AI/ML API"
    icon = "ChatInput" # TODO: Get their icon.

    chat_completion_url = "https://api.aimlapi.com/v1/chat/completions"

    models = [
        "meta-llama/Llama-2-70b-chat-hf",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-davinci",
    ]

    outputs = [
        Output(display_name="Text", name="text_output", method="make_request"),
    ]

    inputs = [
        MessageInput(name="input_value", display_name="Input"),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        DictInput(
            name="output_schema",
            is_list=True,
            display_name="Schema",
            advanced=True,
            info="The schema for the Output of the model. You must pass the word JSON in the prompt. If left blank, JSON mode will be disabled.",
        ),
        DropdownInput(
            name="model_name", display_name="Model Name", advanced=False, options=models, value=models[0]
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="The OpenAI API Key to use for the OpenAI model.",
            advanced=False,
            value="OPENAI_API_KEY",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
    ]


    async def make_request(self) -> Message:
        output_schema_dict: dict[str, str] = reduce(operator.ior, self.output_schema or {}, {})
        openai_api_key = self.openai_api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        model_kwargs = self.model_kwargs or {}
        json_mode = bool(output_schema_dict) or self.json_mode
        seed = self.seed

        if openai_api_key:
            api_key = SecretStr(openai_api_key)
        else:
            api_key = None

        model_kwargs["seed"] = seed

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # Prepare the request payload
        payload = {
            "max_tokens": max_tokens or None,
            "model_kwargs": model_kwargs,
            "model": model_name,
            "temperature": temperature or 0.1,
            "messages" : [
                {
                    "role": "system",
                    "content": self.system_message
                },
                {
                    "role": "user",
                    "content": self.input_value.text
                }
            ]
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.chat_completion_url, headers=headers, data=json.dumps(payload))
                if response.status_code != 200:
                    raise Exception(f"Request failed with status code {response.status_code} with error: {response.text}")

                try:
                    print(f"Response: {response}")
                    print(f"Response json: {response.json()}")
                    result = response.json()['message']
                except Exception:
                    result = response.text
                    print(f"result text: {result}")

                self.status = result
                return Message(text=result)
            except httpx.TimeoutException:
                return Message(text="Request timed out.")
            except Exception as exc:
                logger.error(f"Error: {exc}")
                raise exc
