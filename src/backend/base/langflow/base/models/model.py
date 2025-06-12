import importlib
import json
import warnings
from abc import abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.llms import LLM
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import BaseOutputParser

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.custom.custom_component.component import Component
from langflow.field_typing import LanguageModel
from langflow.inputs.inputs import BoolInput, InputTypes, MessageInput, MultilineInput
from langflow.schema.message import Message
from langflow.template.field.base import Output

# Enabled detailed thinking for NVIDIA reasoning models.
#
# Models are trained with this exact string. Do not update.
DETAILED_THINKING_PREFIX = "detailed thinking on\n\n"


class LCModelComponent(Component):
    display_name: str = "Model Name"
    description: str = "Model Description"
    trace_type = "llm"
    metadata = {
        "keywords": [
            "model",
            "llm",
            "language model",
            "large language model",
        ],
    }

    # Optional output parser to pass to the runnable. Subclasses may allow the user to input an `output_parser`
    output_parser: BaseOutputParser | None = None

    _base_inputs: list[InputTypes] = [
        MessageInput(name="input_value", display_name="Input"),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=False,
        ),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
    ]

    outputs = [
        Output(display_name="Model Response", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def _get_exception_message(self, e: Exception):
        return str(e)

    def supports_tool_calling(self, model: LanguageModel) -> bool:
        try:
            # Check if the bind_tools method is the same as the base class's method
            if model.bind_tools is BaseChatModel.bind_tools:
                return False

            def test_tool(x: int) -> int:
                return x

            model_with_tool = model.bind_tools([test_tool])
            return hasattr(model_with_tool, "tools") and len(model_with_tool.tools) > 0
        except (AttributeError, TypeError, ValueError):
            return False

    def _validate_outputs(self) -> None:
        # At least these two outputs must be defined
        required_output_methods = ["text_response", "build_model"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                msg = f"Output with name '{method_name}' must be defined."
                raise ValueError(msg)
            if not hasattr(self, method_name):
                msg = f"Method '{method_name}' must be defined."
                raise ValueError(msg)

    def text_response(self) -> Message:
        input_value = self.input_value
        stream = self.stream
        system_message = self.system_message
        output = self.build_model()
        result = self.get_chat_result(
            runnable=output, stream=stream, input_value=input_value, system_message=system_message
        )
        self.status = result
        return result

    def get_result(self, *, runnable: LLM, stream: bool, input_value: str):
        """Retrieves the result from the output of a Runnable object.

        Args:
            runnable (Runnable): The runnable to retrieve the result from.
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
        except Exception as e:
            if message := self._get_exception_message(e):
                raise ValueError(message) from e
            raise

        return result

    def build_status_message(self, message: AIMessage):
        """Builds a status message from an AIMessage object.

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
                status_message = f"Response: {content}"  # type: ignore[assignment]
        else:
            status_message = f"Response: {message.content}"  # type: ignore[assignment]
        return status_message

    def get_chat_result(
        self,
        *,
        runnable: LanguageModel,
        stream: bool,
        input_value: str | Message,
        system_message: str | None = None,
    ) -> Message:
        if getattr(self, "detailed_thinking", False):
            system_message = DETAILED_THINKING_PREFIX + (system_message or "")

        return self._get_chat_result(
            runnable=runnable,
            stream=stream,
            input_value=input_value,
            system_message=system_message,
        )

    def _get_chat_result(
        self,
        *,
        runnable: LanguageModel,
        stream: bool,
        input_value: str | Message,
        system_message: str | None = None,
    ) -> Message:
        messages: list[BaseMessage] = []
        if not input_value and not system_message:
            msg = "The message you want to send to the model is empty."
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
                        runnable = prompt | runnable
                    else:
                        messages.append(input_value.to_lc_message())
            else:
                messages.append(HumanMessage(content=input_value))

        if system_message and not system_message_added:
            messages.insert(0, SystemMessage(content=system_message))
        inputs: list | dict = messages or {}
        try:
            # TODO: Depreciated Feature to be removed in upcoming release
            if hasattr(self, "output_parser") and self.output_parser is not None:
                runnable |= self.output_parser

            runnable = runnable.with_config(
                {
                    "run_name": self.display_name,
                    "project_name": self.get_project_name(),
                    "callbacks": self.get_langchain_callbacks(),
                }
            )
            if stream:
                return runnable.stream(inputs)
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
        except Exception as e:
            if message := self._get_exception_message(e):
                raise ValueError(message) from e
            raise

        return Message(text=result)

    @abstractmethod
    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        """Implement this method to build the model."""

    def get_llm(self, provider_name: str, model_info: dict[str, dict[str, str | list[InputTypes]]]) -> LanguageModel:
        """Get LLM model based on provider name and inputs.

        Args:
            provider_name: Name of the model provider (e.g., "OpenAI", "Azure OpenAI")
            inputs: Dictionary of input parameters for the model
            model_info: Dictionary of model information

        Returns:
            Built LLM model instance
        """
        try:
            if provider_name not in [model.get("display_name") for model in model_info.values()]:
                msg = f"Unknown model provider: {provider_name}"
                raise ValueError(msg)

            # Find the component class name from MODEL_INFO in a single iteration
            component_info, module_name = next(
                ((info, key) for key, info in model_info.items() if info.get("display_name") == provider_name),
                (None, None),
            )
            if not component_info:
                msg = f"Component information not found for {provider_name}"
                raise ValueError(msg)
            component_inputs = component_info.get("inputs", [])
            # Get the component class from the models module
            # Ensure component_inputs is a list of the expected types
            if not isinstance(component_inputs, list):
                component_inputs = []

            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="Support for class-based `config` is deprecated", category=DeprecationWarning
                )
                warnings.filterwarnings("ignore", message="Valid config keys have changed in V2", category=UserWarning)
                models_module = importlib.import_module("langflow.components.models")
                component_class = getattr(models_module, str(module_name))
                component = component_class()

            return self.build_llm_model_from_inputs(component, component_inputs)
        except Exception as e:
            msg = f"Error building {provider_name} language model"
            raise ValueError(msg) from e

    def build_llm_model_from_inputs(
        self, component: Component, inputs: list[InputTypes], prefix: str = ""
    ) -> LanguageModel:
        """Build LLM model from component and inputs.

        Args:
            component: LLM component instance
            inputs: Dictionary of input parameters for the model
            prefix: Prefix for the input names
        Returns:
            Built LLM model instance
        """
        # Ensure prefix is a string
        prefix = prefix or ""
        # Filter inputs to only include valid component input names
        input_data = {
            str(component_input.name): getattr(self, f"{prefix}{component_input.name}", None)
            for component_input in inputs
        }

        return component.set(**input_data).build_model()
