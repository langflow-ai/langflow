import json
from typing import Any, Dict
import httpx
from langflow.components.models.OllamaModel import ChatOllamaComponent
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.custom.custom_component.component import Component

from langflow.schema.dotdict import dotdict
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
    icon = "ChatInput"  # TODO: Get their icon.

    chat_completion_url = "https://api.aimlapi.com/v1/chat/completions"

    models = {
        "gpt-4": "open_ai",
        "gpt-3.5-turbo": "open_ai",
        "gpt-3.5-turbo-davinci": "open_ai",
        "codellama/CodeLlama-13b-Instruct-hf": "llama",
        "codellama/CodeLlama-34b-Instruct-hf": "llama",
        "codellama/CodeLlama-70b-Instruct-hf": "llama",
    }

    def _update_inputs(self, build_config, to_add):
        for input in to_add:
            # Don't include the `model_name` or `input_value` fields, as they are
            # available by default.
             # TODO: this hard coding nonsense is brittle. Either have good tests, or figure out
                    # a better way to do this.
            if input.name == "model_name":
                continue

            build_config[input.name] = input.to_dict()

    def _remove_inputs(self, build_config, to_remove):
        for input in to_remove:
            if input.name == "model_name":
                continue
            if input.name in build_config:
                build_config.pop(input.name)

    def _update_build_config(self, build_config, field_value):
        build_config["_provider"]['value'] = self.models[field_value]
        if self.models[field_value] == "open_ai":
            self._update_inputs(build_config, OpenAIModelComponent.inputs)
        elif self.models[field_value] == "llama":
            self._update_inputs(build_config, ChatOllamaComponent.inputs)


    def update_build_config(
        self,
        build_config: dotdict,
        field_value: Any,
        field_name: str | None = None,
    ):
        if field_name == "model_name":
            # Remove and update the inputs based on the model selected
            if build_config["_provider"] is not None and build_config["_provider"]['value'] != "":
                if build_config['_provider']['value'] == "open_ai" and self.models[field_value] != "open_ai":
                    self._remove_inputs(build_config, OpenAIModelComponent.inputs)
                    self._update_build_config(build_config, field_value)

                if build_config['_provider']['value'] == "llama" and self.models[field_value] != "llama":
                    self._remove_inputs(build_config, ChatOllamaComponent.inputs)
                    self._update_build_config(build_config, field_value)
            else:
                # First time update - set the inputs
                self._update_build_config(build_config, field_value)

        return build_config

    outputs = [
        Output(display_name="Text", name="text_output", method="make_request"),
    ]

    inputs = [
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=list(models.keys()),
            # value="gpt-4", # If I don't provide a default, I don't have to populate the initial input :shrug:
            real_time_refresh=True,
        ),
        StrInput(name="_provider", show=False, info="Tracks the provider of the model; used for input updates"),
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
            "Authorization": f"Bearer {api_key.get_secret_value()}" if api_key else "",
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
            response = requests.post(
                self.chat_completion_url, headers=headers, data=json.dumps(payload)
            )
            try:
                response.raise_for_status()  # Raise an error for bad status codes
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
