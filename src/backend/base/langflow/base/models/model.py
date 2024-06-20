import json
import warnings
from typing import Optional, Union

from langchain_core.language_models.llms import LLM
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from langflow.base.models.exceptions import get_message_from_openai_exception
from langflow.custom import Component
from langflow.field_typing import LanguageModel
from langflow.schema.message import Message


class LCModelComponent(Component):
    display_name: str = "Model Name"
    description: str = "Model Description"

    def get_result(self, runnable: LLM, stream: bool, input_value: str):
        """
        Retrieves the result from the output of a Runnable object.

        Args:
            output (Runnable): The output object to retrieve the result from.
            stream (bool): Indicates whether to use streaming or invocation mode.
            input_value (str): The input value to pass to the output object.

        Returns:
            The result obtained from the output object.
        """
        try:
            if stream:
                result = runnable.stream(input_value)
            else:
                message = runnable.invoke(input_value)
                result = message.content if hasattr(message, "content") else message
                self.status = result
            return result
        except Exception as e:
            if message := get_message_from_openai_exception(e):
                raise ValueError(message)
            raise e

    def build_status_message(self, message: AIMessage):
        """
        Builds a status message from an AIMessage object.

        Args:
            message (AIMessage): The AIMessage object to build the status message from.

        Returns:
            The status message.
        """
        if message.response_metadata:
            # Build a well formatted status message
            content = message.content
            response_metadata = message.response_metadata
            openai_keys = ["token_usage", "model_name", "finish_reason"]
            inner_openai_keys = ["completion_tokens", "prompt_tokens", "total_tokens"]
            anthropic_keys = ["model", "usage", "stop_reason"]
            inner_anthropic_keys = ["input_tokens", "output_tokens"]
            if all(key in response_metadata for key in openai_keys) and all(
                key in response_metadata["token_usage"] for key in inner_openai_keys
            ):
                token_usage = response_metadata["token_usage"]
                status_message = {
                    "tokens": {
                        "input": token_usage["prompt_tokens"],
                        "output": token_usage["completion_tokens"],
                        "total": token_usage["total_tokens"],
                        "stop_reason": response_metadata["finish_reason"],
                        "response": content,
                    }
                }

            elif all(key in response_metadata for key in anthropic_keys) and all(
                key in response_metadata["usage"] for key in inner_anthropic_keys
            ):
                usage = response_metadata["usage"]
                status_message = {
                    "tokens": {
                        "input": usage["input_tokens"],
                        "output": usage["output_tokens"],
                        "stop_reason": response_metadata["stop_reason"],
                        "response": content,
                    }
                }
            else:
                status_message = f"Response: {content}"  # type: ignore
        else:
            status_message = f"Response: {message.content}"  # type: ignore
        return status_message

    def get_chat_result(
        self, runnable: LanguageModel, stream: bool, input_value: str | Message, system_message: Optional[str] = None
    ):
        messages: list[Union[HumanMessage, SystemMessage]] = []
        if not input_value and not system_message:
            raise ValueError("The message you want to send to the model is empty.")
        if system_message:
            messages.append(SystemMessage(content=system_message))
        if input_value:
            if isinstance(input_value, Message):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if "prompt" in input_value:
                        prompt = input_value.load_lc_prompt()
                        runnable = prompt | runnable
                    else:
                        messages.append(input_value.to_lc_message())
            else:
                messages.append(HumanMessage(content=input_value))
        inputs = messages or {}
        try:
            if stream:
                return runnable.stream(inputs)
            else:
                message = runnable.invoke(inputs)
                result = message.content if hasattr(message, "content") else message
                if isinstance(message, AIMessage):
                    status_message = self.build_status_message(message)
                    self.status = status_message
                elif isinstance(result, dict):
                    result = json.dumps(message, indent=4)
                    self.status = result
                else:
                    self.status = result
                return result
        except Exception as e:
            if message := get_message_from_openai_exception(e):
                raise ValueError(message)
            raise e
