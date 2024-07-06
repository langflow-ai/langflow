import json
import os
import time
from typing import Any, Dict, List, Optional, Sequence, Type, Union

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.pydantic_v1 import BaseConfig, BaseModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from langflow.custom import CustomComponent
from langflow.field_typing import LanguageModel
from langflow.schema.message import Message

from cognite.client import CogniteClient, ClientConfig
from cognite.client.credentials import OAuthClientCredentials


class CogniteOpenAI(CustomComponent):
    display_name = "Cognite OpenAI"
    description = "OpenAI model through the Cognite API"

    def build_config(self) -> dict:
        models = ["gpt-4-32k", "gpt-35-turbo-16k"]
        return {
            "model": {"display_name": "Model", "options": models, "value": models[0]},
            "temperature": {"display_name": "Temperature", "value": 0.0},
            "max_tokens": {"display_name": "Max Tokens", "value": 30000},
        }

    def build(self, model: str, temperature: float, max_tokens: int) -> LanguageModel:
        return self.CogniteChatOpenAI(model=model, temperature=temperature, max_tokens=max_tokens)


    class CogniteChatOpenAI(BaseChatModel):
        model: str
        temperature: float
        max_tokens: int
        tools: list[dict[str, Any]] = []

        @property
        def _llm_type(self) -> str:
            return "awesome"

        def bind_tools(
            self,
            tools: Sequence[Union[Dict[str, Any], Type[BaseModel], Callable, BaseTool]],
            **kwargs: Any,
        ) -> Runnable[LanguageModelInput, BaseMessage]:
            print("bind_tools")
            print(tools)
            formatted_tools = [convert_to_openai_tool(tool) for tool in tools]
            print(formatted_tools)
            self.tools = formatted_tools
            return super().bind(tools=formatted_tools, **kwargs)

        def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:
            print(f"_generate({messages}, {stop}, {run_manager})")

            body = {
                "messages": self._convert_messages(messages),
                "functions": [tool["function"] for tool in self.tools],
                "model": self.model,
                "temperature": self.temperature,
                "maxTokens": self.max_tokens,
            }
            print(body)

            response = self._request_with_retry(body)
            response_json = response.json()
            print(json.dumps(response_json, indent=2))

            generations = []
            choices = response_json["choices"]
            for choice in choices:
                message = choice["message"]
                content = message.get("content", "")
                name, tool_calls = self._parse_tool_calls(message.get("functionCall"))
                generation = ChatGeneration(message=AIMessage(content=content, name=name, tool_calls=tool_calls))
                generations.append(generation)

            return ChatResult(generations=generations)

        def _parse_tool_calls(self, function_call: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
            if function_call is None:
                return None, []

            name = function_call["name"]

            parsed = {
                "name": name,
                "args": json.loads(function_call["arguments"]),
                "id": "foo",
            }
            return name, [parsed]

        def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
            system_message = []
            other_messages = []
            for message in messages:
                if message.type == "system":
                    if len(system_message) == 0:
                        system_message = [message]
                else:
                    other_messages.append(message)

            return [self._convert_message(message) for message in system_message + other_messages[-9:]]


        def _convert_message(self, message: BaseMessage) -> Dict[str, Any]:
            role_lookup = {
                "system": "system",
                "human": "user",
                "ai": "assistant",
                "tool": "function",
            }

            role = role_lookup[message.type]

            if role == "function":
                return {
                    "role": role,
                    "name": message.name or "semantic_search", # TODO: Remove hack
                    "content": message.content,
                }

            return {
                "role": role,
                "content": message.content,
            }

        def _request_with_retry(self, body):
            project = os.environ["COGNITE_PROJECT"]
            client = CogniteClient(
                config=ClientConfig(
                    client_name=__file__,
                    project=project,
                    base_url=os.environ["COGNITE_BASE_URL"],
                    credentials=OAuthClientCredentials(
                        token_url=os.environ["COGNITE_TOKEN_URL"],
                        client_id=os.environ["COGNITE_CLIENT_ID"],
                        client_secret=os.environ["COGNITE_CLIENT_SECRET"],
                        scopes=[os.environ["COGNITE_TOKEN_SCOPES"]],
                    )
                )
            )
            url = f"/api/v1/projects/{project}/ai/chat/completions"

            while True:
                try:
                    return client.post(url, json=body)
                except Exception as e:
                    print(e)
                    time.sleep(5)


