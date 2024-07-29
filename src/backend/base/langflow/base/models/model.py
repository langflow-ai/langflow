import json
import warnings
from abc import abstractmethod
from typing import Optional, Union, List

from langchain_core.language_models.llms import LLM
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.custom import Component
from langflow.field_typing import LanguageModel
from langflow.inputs import MessageInput, MessageTextInput
from langflow.inputs.inputs import InputTypes, BoolInput
from langflow.schema.message import Message
from langflow.template.field.base import Output


class LCModelComponent(Component):
    display_name: str = "Model Name"
    description: str = "Model Description"
    trace_type = "llm"

    _base_inputs: List[InputTypes] = [
        MessageInput(name="input_value", display_name="Input"),
        MessageTextInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
    ]

    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def _get_exception_message(self, e: Exception):
        return str(e)

    def _validate_outputs(self):
        # At least these two outputs must be defined
        required_output_methods = ["text_response", "build_model"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                raise ValueError(f"Output with name '{method_name}' must be defined.")
            elif not hasattr(self, method_name):
                raise ValueError(f"Method '{method_name}' must be defined.")

    def text_response(self) -> Message:
        input_value = self.input_value
        stream = self.stream
        system_message = self.system_message
        output = self.build_model()
        result = self.get_chat_result(output, stream, input_value, system_message)
        self.status = result
        return result

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
            if message := self._get_exception_message(e):
                raise ValueError(message) from e
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
        self,
        runnable: LanguageModel,
        stream: bool,
        input_value: str | Message,
        system_message: Optional[str] = None,
    ):
        messages: list[Union[BaseMessage]] = []
        if not input_value and not system_message:
            raise ValueError("The message you want to send to the model is empty.")
        system_message_added = False
        if input_value:
            if isinstance(input_value, Message):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if "prompt" in input_value:
                        prompt = input_value.load_lc_prompt()
                        if system_message:
                            prompt.messages = [SystemMessage(content=system_message)] + prompt.messages
                            system_message_added = True
                        runnable = prompt | runnable
                    else:
                        messages.append(input_value.to_lc_message())
            else:
                messages.append(HumanMessage(content=input_value))

        if system_message and not system_message_added:
            messages.append(SystemMessage(content=system_message))
        inputs: Union[list, dict] = messages or {}
        try:
            runnable = runnable.with_config(  # type: ignore
                {"run_name": self.display_name, "project_name": self.tracing_service.project_name}  # type: ignore
            )
            if stream:
                return runnable.stream(inputs)  # type: ignore
            else:
                message = runnable.invoke(inputs)  # type: ignore
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
            if message := self._get_exception_message(e):
                raise ValueError(message) from e
            raise e

    @abstractmethod
    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        """
        Implement this method to build the model.
        """
