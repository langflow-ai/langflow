import json
from typing import Any, Dict
import httpx
from langflow.base.models.aiml_constants import MODEL_NAMES
from langflow.components.models.MistralModel import MistralAIModelComponent
from langflow.components.models.OllamaModel import ChatOllamaComponent
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.custom.custom_component.component import Component

from langflow.inputs.inputs import FloatInput, IntInput, MessageInput, SecretStrInput
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message
from langflow.template.field.base import Output
from loguru import logger
from pydantic.v1 import SecretStr

from langflow.inputs import (
    DropdownInput,
    StrInput,
)
import requests


class AIMLModelComponent(Component):
    display_name = "AI/ML API"
    description = "Generates text using the AI/ML API"
    icon = "ChatInput"  # TODO: Get their icon.
    chat_completion_url = "https://api.aimlapi.com/v1/chat/completions"

    outputs = [
        Output(display_name="Text", name="text_output", method="make_request"),
    ]

    inputs = [
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=MODEL_NAMES,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="aiml_api_key",
            display_name="AI/ML API Key",
            value="AIML_API_KEY",
        ),
        MessageInput(name="input_value", display_name="Input", required=True),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        StrInput(
            name="stop_tokens",
            display_name="Stop Tokens",
            info="Comma-separated list of tokens to signal the model to stop generating text.",
            advanced=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            info="Limits token selection to top K. (Default: 40)",
            advanced=True,
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="Works together with top-k. (Default: 0.9)",
            advanced=True,
        ),
        FloatInput(
            name="repeat_penalty",
            display_name="Repeat Penalty",
            info="Penalty for repetitions in generated text. (Default: 1.1)",
            advanced=True,
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            value=0.2,
            info="Controls the creativity of model responses.",
        ),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
    ]

    def make_request(self) -> Message:
        api_key = SecretStr(self.aiml_api_key) if self.aiml_api_key else None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key.get_secret_value()}" if api_key else "",
        }

        messages = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})

        if self.input_value:
            if isinstance(self.input_value, Message):
                # Though we aren't using langchain here, the helper method is useful
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
            "model": self.model_name,
            "messages": messages,
            "max_tokens": self.max_tokens or None,
            "temperature": self.temperature or 0.2,
            "top_k": self.top_k or 40,
            "top_p": self.top_p or 0.9,
            "repeat_penalty": self.repeat_penalty or 1.1,
            "stop_tokens": self.stop_tokens or None,
        }

        try:
            response = requests.post(
                self.chat_completion_url, headers=headers, data=json.dumps(payload)
            )
            try:
                response.raise_for_status()
                result_data = response.json()
                choice = result_data["choices"][0]
                result = choice["message"]["content"]
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
