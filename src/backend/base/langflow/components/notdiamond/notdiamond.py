import warnings

import requests
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from lfx.custom.custom_component.component import Component
from pydantic.v1 import SecretStr

from langflow.base.models.chat_result import get_chat_result
from langflow.base.models.model_utils import get_model_name
from langflow.io import (
    BoolInput,
    DropdownInput,
    HandleInput,
    MessageInput,
    MessageTextInput,
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema.message import Message

ND_MODEL_MAPPING = {
    "gpt-4o": {"provider": "openai", "model": "gpt-4o"},
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "gpt-4-turbo": {"provider": "openai", "model": "gpt-4-turbo-2024-04-09"},
    "claude-3-5-haiku-20241022": {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
    "claude-3-5-sonnet-20241022": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
    "anthropic.claude-3-5-haiku-20241022-v1:0": {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
    "gemini-1.5-pro": {"provider": "google", "model": "gemini-1.5-pro-latest"},
    "gemini-1.5-flash": {"provider": "google", "model": "gemini-1.5-flash-latest"},
    "llama-3.1-sonar-large-128k-online": {"provider": "perplexity", "model": "llama-3.1-sonar-large-128k-online"},
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": {
        "provider": "togetherai",
        "model": "Meta-Llama-3.1-70B-Instruct-Turbo",
    },
    "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": {
        "provider": "togetherai",
        "model": "Meta-Llama-3.1-405B-Instruct-Turbo",
    },
    "mistral-large-latest": {"provider": "mistral", "model": "mistral-large-2407"},
}


class NotDiamondComponent(Component):
    display_name = "Not Diamond Router"
    description = "Call the right model at the right time with the world's most powerful AI model router."
    documentation: str = "https://docs.notdiamond.ai/"
    icon = "NotDiamond"
    name = "NotDiamond"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._selected_model_name = None

    inputs = [
        MessageInput(name="input_value", display_name="Input", required=True),
        MessageTextInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=False,
        ),
        HandleInput(
            name="models",
            display_name="Language Models",
            input_types=["LanguageModel"],
            required=True,
            is_list=True,
            info="Link the models you want to route between.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Not Diamond API Key",
            info="The Not Diamond API Key to use for routing.",
            advanced=False,
            value="NOTDIAMOND_API_KEY",
            required=True,
        ),
        StrInput(
            name="preference_id",
            display_name="Preference ID",
            info="The ID of the router preference that was configured via the Dashboard.",
            advanced=False,
        ),
        DropdownInput(
            name="tradeoff",
            display_name="Tradeoff",
            info="The tradeoff between cost and latency for the router to determine the best LLM for a given query.",
            advanced=False,
            options=["quality", "cost", "latency"],
            value="quality",
        ),
        BoolInput(
            name="hash_content",
            display_name="Hash Content",
            info="Whether to hash the content before being sent to the NotDiamond API.",
            advanced=False,
            value=False,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="model_select"),
        Output(
            display_name="Selected Model",
            name="selected_model",
            method="get_selected_model",
            required_inputs=["output"],
        ),
    ]

    def get_selected_model(self) -> str:
        return self._selected_model_name

    def model_select(self) -> Message:
        api_key = SecretStr(self.api_key).get_secret_value() if self.api_key else None
        input_value = self.input_value
        system_message = self.system_message
        messages = self._format_input(input_value, system_message)

        selected_models = []
        mapped_selected_models = []
        for model in self.models:
            model_name = get_model_name(model)

            if model_name in ND_MODEL_MAPPING:
                selected_models.append(model)
                mapped_selected_models.append(ND_MODEL_MAPPING[model_name])

        payload = {
            "messages": messages,
            "llm_providers": mapped_selected_models,
            "hash_content": self.hash_content,
        }

        if self.tradeoff != "quality":
            payload["tradeoff"] = self.tradeoff

        if self.preference_id and self.preference_id != "":
            payload["preference_id"] = self.preference_id

        header = {
            "Authorization": f"Bearer {api_key}",
            "accept": "application/json",
            "content-type": "application/json",
        }

        response = requests.post(
            "https://api.notdiamond.ai/v2/modelRouter/modelSelect",
            json=payload,
            headers=header,
            timeout=10,
        )

        result = response.json()
        chosen_model = self.models[0]  # By default there is a fallback model
        self._selected_model_name = get_model_name(chosen_model)

        if "providers" not in result:
            # No provider returned by NotDiamond API, likely failed. Fallback to first model.
            return self._call_get_chat_result(chosen_model, input_value, system_message)

        providers = result["providers"]

        if len(providers) == 0:
            # No provider returned by NotDiamond API, likely failed. Fallback to first model.
            return self._call_get_chat_result(chosen_model, input_value, system_message)

        nd_result = providers[0]

        for nd_model, selected_model in zip(mapped_selected_models, selected_models, strict=False):
            if nd_model["provider"] == nd_result["provider"] and nd_model["model"] == nd_result["model"]:
                chosen_model = selected_model
                self._selected_model_name = get_model_name(chosen_model)
                break

        return self._call_get_chat_result(chosen_model, input_value, system_message)

    def _call_get_chat_result(self, chosen_model, input_value, system_message):
        return get_chat_result(
            runnable=chosen_model,
            input_value=input_value,
            system_message=system_message,
        )

    def _format_input(
        self,
        input_value: str | Message,
        system_message: str | None = None,
    ):
        messages: list[BaseMessage] = []
        if not input_value and not system_message:
            msg = "The message you want to send to the router is empty."
            raise ValueError(msg)
        system_message_added = False
        if input_value:
            if isinstance(input_value, Message):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if "prompt" in input_value:
                        prompt = input_value.load_lc_prompt()
                        if system_message:
                            prompt.messages = [
                                SystemMessage(content=system_message),
                                *prompt.messages,  # type: ignore[has-type]
                            ]
                            system_message_added = True
                        messages.extend(prompt.messages)
                    else:
                        messages.append(input_value.to_lc_message())
            else:
                messages.append(HumanMessage(content=input_value))

        if system_message and not system_message_added:
            messages.insert(0, SystemMessage(content=system_message))

        # Convert Langchain messages to OpenAI format
        openai_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                openai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                openai_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                openai_messages.append({"role": "system", "content": msg.content})

        return openai_messages
