from typing import Any, Dict, List, Optional

# from langchain_community.chat_models import ChatOllama
from langchain_community.chat_models import ChatOllama

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent

# from langchain.chat_models import ChatOllama
from langflow.field_typing import Text

# whe When a callback component is added to Langflow, the comment must be uncommented.
# from langchain.callbacks.manager import CallbackManager


class ChatOllamaComponent(LCModelComponent):
    display_name = "Ollama"
    description = "Generate text using Ollama Local LLMs."
    icon = "Ollama"

    field_order = [
        "base_url",
        "model",
        "temperature",
        "cache",
        "callback_manager",
        "callbacks",
        "format",
        "metadata",
        "mirostat",
        "mirostat_eta",
        "mirostat_tau",
        "num_ctx",
        "num_gpu",
        "num_thread",
        "repeat_last_n",
        "repeat_penalty",
        "tfs_z",
        "timeout",
        "top_k",
        "top_p",
        "verbose",
        "tags",
        "stop",
        "system",
        "template",
        "input_value",
        "system_message",
        "stream",
    ]

    def build_config(self) -> dict:
        return {
            "base_url": {
                "display_name": "Base URL",
                "info": "Endpoint of the Ollama API. Defaults to 'http://localhost:11434' if not specified.",
                "advanced": True,
            },
            "model": {
                "display_name": "Model Name",
                "value": "llama2",
                "info": "Refer to https://ollama.ai/library for more models.",
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "value": 0.8,
                "info": "Controls the creativity of model responses.",
            },
            "cache": {
                "display_name": "Cache",
                "field_type": "bool",
                "info": "Enable or disable caching.",
                "advanced": True,
                "value": False,
            },
            ### When a callback component is added to Langflow, the comment must be uncommented. ###
            # "callback_manager": {
            #     "display_name": "Callback Manager",
            #     "info": "Optional callback manager for additional functionality.",
            #     "advanced": True,
            # },
            # "callbacks": {
            #     "display_name": "Callbacks",
            #     "info": "Callbacks to execute during model runtime.",
            #     "advanced": True,
            # },
            ########################################################################################
            "format": {
                "display_name": "Format",
                "field_type": "str",
                "info": "Specify the format of the output (e.g., json).",
                "advanced": True,
            },
            "metadata": {
                "display_name": "Metadata",
                "info": "Metadata to add to the run trace.",
                "advanced": True,
            },
            "mirostat": {
                "display_name": "Mirostat",
                "options": ["Disabled", "Mirostat", "Mirostat 2.0"],
                "info": "Enable/disable Mirostat sampling for controlling perplexity.",
                "value": "Disabled",
                "advanced": True,
            },
            "mirostat_eta": {
                "display_name": "Mirostat Eta",
                "field_type": "float",
                "info": "Learning rate for Mirostat algorithm. (Default: 0.1)",
                "advanced": True,
            },
            "mirostat_tau": {
                "display_name": "Mirostat Tau",
                "field_type": "float",
                "info": "Controls the balance between coherence and diversity of the output. (Default: 5.0)",
                "advanced": True,
            },
            "num_ctx": {
                "display_name": "Context Window Size",
                "field_type": "int",
                "info": "Size of the context window for generating tokens. (Default: 2048)",
                "advanced": True,
            },
            "num_gpu": {
                "display_name": "Number of GPUs",
                "field_type": "int",
                "info": "Number of GPUs to use for computation. (Default: 1 on macOS, 0 to disable)",
                "advanced": True,
            },
            "num_thread": {
                "display_name": "Number of Threads",
                "field_type": "int",
                "info": "Number of threads to use during computation. (Default: detected for optimal performance)",
                "advanced": True,
            },
            "repeat_last_n": {
                "display_name": "Repeat Last N",
                "field_type": "int",
                "info": "How far back the model looks to prevent repetition. (Default: 64, 0 = disabled, -1 = num_ctx)",
                "advanced": True,
            },
            "repeat_penalty": {
                "display_name": "Repeat Penalty",
                "field_type": "float",
                "info": "Penalty for repetitions in generated text. (Default: 1.1)",
                "advanced": True,
            },
            "tfs_z": {
                "display_name": "TFS Z",
                "field_type": "float",
                "info": "Tail free sampling value. (Default: 1)",
                "advanced": True,
            },
            "timeout": {
                "display_name": "Timeout",
                "field_type": "int",
                "info": "Timeout for the request stream.",
                "advanced": True,
            },
            "top_k": {
                "display_name": "Top K",
                "field_type": "int",
                "info": "Limits token selection to top K. (Default: 40)",
                "advanced": True,
            },
            "top_p": {
                "display_name": "Top P",
                "field_type": "float",
                "info": "Works together with top-k. (Default: 0.9)",
                "advanced": True,
            },
            "verbose": {
                "display_name": "Verbose",
                "field_type": "bool",
                "info": "Whether to print out response text.",
            },
            "tags": {
                "display_name": "Tags",
                "field_type": "list",
                "info": "Tags to add to the run trace.",
                "advanced": True,
            },
            "stop": {
                "display_name": "Stop Tokens",
                "field_type": "list",
                "info": "List of tokens to signal the model to stop generating text.",
                "advanced": True,
            },
            "system": {
                "display_name": "System",
                "field_type": "str",
                "info": "System to use for generating text.",
                "advanced": True,
            },
            "template": {
                "display_name": "Template",
                "field_type": "str",
                "info": "Template to use for generating text.",
                "advanced": True,
            },
            "input_value": {"display_name": "Input"},
            "stream": {
                "display_name": "Stream",
                "info": STREAM_INFO_TEXT,
            },
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "advanced": True,
            },
        }

    def build(
        self,
        base_url: Optional[str],
        model: str,
        input_value: Text,
        mirostat: Optional[str],
        mirostat_eta: Optional[float] = None,
        mirostat_tau: Optional[float] = None,
        ### When a callback component is added to Langflow, the comment must be uncommented.###
        # callback_manager: Optional[CallbackManager] = None,
        # callbacks: Optional[List[Callbacks]] = None,
        #######################################################################################
        repeat_last_n: Optional[int] = None,
        verbose: Optional[bool] = None,
        cache: Optional[bool] = None,
        num_ctx: Optional[int] = None,
        num_gpu: Optional[int] = None,
        format: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        num_thread: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[List[str]] = None,
        system: Optional[str] = None,
        tags: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        template: Optional[str] = None,
        tfs_z: Optional[float] = None,
        timeout: Optional[int] = None,
        top_k: Optional[int] = None,
        top_p: Optional[int] = None,
        stream: bool = False,
        system_message: Optional[str] = None,
    ) -> Text:
        if not base_url:
            base_url = "http://localhost:11434"

        # Mapping mirostat settings to their corresponding values
        mirostat_options = {"Mirostat": 1, "Mirostat 2.0": 2}

        # Default to 0 for 'Disabled'
        mirostat_value = mirostat_options.get(mirostat, 0)  # type: ignore

        # Set mirostat_eta and mirostat_tau to None if mirostat is disabled
        if mirostat_value == 0:
            mirostat_eta = None
            mirostat_tau = None

        # Mapping system settings to their corresponding values
        llm_params = {
            "base_url": base_url,
            "cache": cache,
            "model": model,
            "mirostat": mirostat_value,
            "format": format,
            "metadata": metadata,
            "tags": tags,
            ## When a callback component is added to Langflow, the comment must be uncommented.##
            # "callback_manager": callback_manager,
            # "callbacks": callbacks,
            #####################################################################################
            "mirostat_eta": mirostat_eta,
            "mirostat_tau": mirostat_tau,
            "num_ctx": num_ctx,
            "num_gpu": num_gpu,
            "num_thread": num_thread,
            "repeat_last_n": repeat_last_n,
            "repeat_penalty": repeat_penalty,
            "temperature": temperature,
            "stop": stop,
            "system": system,
            "template": template,
            "tfs_z": tfs_z,
            "timeout": timeout,
            "top_k": top_k,
            "top_p": top_p,
            "verbose": verbose,
        }

        # None Value remove
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            output = ChatOllama(**llm_params)  # type: ignore
        except Exception as e:
            raise ValueError("Could not initialize Ollama LLM.") from e

        return self.get_chat_result(output, stream, input_value, system_message)
