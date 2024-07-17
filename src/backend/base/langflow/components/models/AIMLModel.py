import json
import operator
from functools import reduce
from typing import Dict
import httpx
from langflow.custom.custom_component.component import Component

from langflow.schema.message import Message
from langflow.template.field.base import Output
from loguru import logger
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
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
        "gpt-4",
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
            name="aiml_api_key",
            display_name="AI/ML API Key",
            info="The AI/ML API Key to use.",
            value="AIML_API_KEY",
            advanced=False,
            required=True,
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

    def make_request(self) -> Message:
        output_schema_dict: Dict[str, str] = {}
        for d in self.output_schema or {}:
            output_schema_dict |= d

        api_key = SecretStr(self.aiml_api_key) if self.aiml_api_key else None

        model_kwargs = self.model_kwargs or {}
        model_kwargs["seed"] = self.seed

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.get_secret_value()}" if api_key else ""
        }

        messages = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})

        if self.input_value:
            if isinstance(self.input_value, Message):
                message = self.input_value.to_lc_message()
                if message.type == "human":
                    messages.append({"role": "user", "content": message.content})
                else:
                    raise ValueError(f"Expected user message, saw: {message.type}")
            else:
                raise TypeError(f"Expected Message type, saw: {type(self.input_value)}")
        else:
            raise ValueError("Please provide an input value")

        payload = {
            "max_tokens": self.max_tokens or None,
            "model_kwargs": model_kwargs,
            "model": self.model_name,
            "temperature": self.temperature or 0.1,
            "messages": messages,
        }

        if bool(output_schema_dict) or self.json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(self.chat_completion_url, headers=headers, data=json.dumps(payload))
            try:
                response.raise_for_status()  # Raise an error for bad status codes
                result_data = response.json()
                choice = result_data['choices'][0]
                result = choice['message']['content']
            except requests.exceptions.HTTPError as http_err:
                logger.error(f"HTTP error occurred: {http_err}")
                raise http_err
            except requests.exceptions.RequestException as req_err:
                logger.error(f"Request error occurred: {req_err}")
                raise req_err
            except json.JSONDecodeError:
                logger.warning("Failed to decode JSON, response text: {response.text}")
                result = response.text
            except KeyError as key_err:
                logger.warning(f"Key error: {key_err}, response content: {result_data}")
                raise key_err

            self.status = result
        except httpx.TimeoutException:
            return Message(text="Request timed out.")
        except Exception as exc:
            logger.error(f"Error: {exc}")
            raise

        return Message(text=result)
