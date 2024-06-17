
from langchain_community.chat_models import ChatOllama
from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import BaseLanguageModel, Text
from langflow.inputs import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, StrInput
from langflow.template import Output

class ChatOllamaComponent(LCModelComponent):
    display_name = "Ollama"
    description = "Generate text using Ollama Local LLMs."
    icon = "Ollama"

    inputs = [
        StrInput(
            name="base_url",
            display_name="Base URL",
            info="Endpoint of the Ollama API. Defaults to 'http://localhost:11434' if not specified.",
            advanced=True,
        ),
        StrInput(
            name="model",
            display_name="Model Name",
            value="llama2",
            info="Refer to https://ollama.ai/library for more models.",
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            value=0.8,
            info="Controls the creativity of model responses.",
        ),
        StrInput(
            name="format",
            display_name="Format",
            info="Specify the format of the output (e.g., json).",
            advanced=True,
        ),
        DictInput(
            name="metadata",
            display_name="Metadata",
            info="Metadata to add to the run trace.",
            advanced=True,
        ),
        DropdownInput(
            name="mirostat",
            display_name="Mirostat",
            options=["Disabled", "Mirostat", "Mirostat 2.0"],
            info="Enable/disable Mirostat sampling for controlling perplexity.",
            value="Disabled",
            advanced=True,
        ),
        FloatInput(
            name="mirostat_eta",
            display_name="Mirostat Eta",
            info="Learning rate for Mirostat algorithm. (Default: 0.1)",
            advanced=True,
        ),
        FloatInput(
            name="mirostat_tau",
            display_name="Mirostat Tau",
            info="Controls the balance between coherence and diversity of the output. (Default: 5.0)",
            advanced=True,
        ),
        IntInput(
            name="num_ctx",
            display_name="Context Window Size",
            info="Size of the context window for generating tokens. (Default: 2048)",
            advanced=True,
        ),
        IntInput(
            name="num_gpu",
            display_name="Number of GPUs",
            info="Number of GPUs to use for computation. (Default: 1 on macOS, 0 to disable)",
            advanced=True,
        ),
        IntInput(
            name="num_thread",
            display_name="Number of Threads",
            info="Number of threads to use during computation. (Default: detected for optimal performance)",
            advanced=True,
        ),
        IntInput(
            name="repeat_last_n",
            display_name="Repeat Last N",
            info="How far back the model looks to prevent repetition. (Default: 64, 0 = disabled, -1 = num_ctx)",
            advanced=True,
        ),
        FloatInput(
            name="repeat_penalty",
            display_name="Repeat Penalty",
            info="Penalty for repetitions in generated text. (Default: 1.1)",
            advanced=True,
        ),
        FloatInput(
            name="tfs_z",
            display_name="TFS Z",
            info="Tail free sampling value. (Default: 1)",
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for the request stream.",
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
        BoolInput(
            name="verbose",
            display_name="Verbose",
            info="Whether to print out response text.",
        ),
        StrInput(
            name="tags",
            display_name="Tags",
            info="Comma-separated list of tags to add to the run trace.",
            advanced=True,
        ),
        StrInput(
            name="stop",
            display_name="Stop Tokens",
            info="Comma-separated list of tokens to signal the model to stop generating text.",
            advanced=True,
        ),
        StrInput(
            name="system",
            display_name="System",
            info="System to use for generating text.",
            advanced=True,
        ),
        StrInput(
            name="template",
            display_name="Template",
            info="Template to use for generating text.",
            advanced=True,
        ),
        StrInput(
            name="input_value",
            display_name="Input",
            input_types=["Text", "Data", "Prompt"],
        ),
        BoolInput(
            name="stream",
            display_name="Stream",
            info=STREAM_INFO_TEXT,
        ),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def text_response(self) -> Text:
        input_value = self.input_value
        stream = self.stream
        system_message = self.system_message
        output = self.build_model()
        result = self.get_chat_result(output, stream, input_value, system_message)
        self.status = result
        return result

    def build_model(self) -> BaseLanguageModel:
        # Mapping mirostat settings to their corresponding values
        mirostat_options = {"Mirostat": 1, "Mirostat 2.0": 2}

        # Default to 0 for 'Disabled'
        mirostat_value = mirostat_options.get(self.mirostat, 0)  # type: ignore

        # Set mirostat_eta and mirostat_tau to None if mirostat is disabled
        if mirostat_value == 0:
            mirostat_eta = None
            mirostat_tau = None
        else:
            mirostat_eta = self.mirostat_eta
            mirostat_tau = self.mirostat_tau

        # Mapping system settings to their corresponding values
        llm_params = {
            "base_url": self.base_url,
            "model": self.model,
            "mirostat": mirostat_value,
            "format": self.format,
            "metadata": self.metadata,
            "tags": self.tags.split(",") if self.tags else None,
            "mirostat_eta": mirostat_eta,
            "mirostat_tau": mirostat_tau,
            "num_ctx": self.num_ctx or None,
            "num_gpu": self.num_gpu or None,
            "num_thread": self.num_thread or None,
            "repeat_last_n": self.repeat_last_n or None,
            "repeat_penalty": self.repeat_penalty or None,
            "temperature": self.temperature or None,
            "stop": self.stop.split(",") if self.stop else None,
            "system": self.system,
            "template": self.template,
            "tfs_z": self.tfs_z or None,
            "timeout": self.timeout or None,
            "top_k": self.top_k or None,
            "top_p": self.top_p or None,
            "verbose": self.verbose,
        }

        # Remove parameters with None values
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            output = ChatOllama(**llm_params)  # type: ignore
        except Exception as e:
            raise ValueError("Could not initialize Ollama LLM.") from e

        return output
