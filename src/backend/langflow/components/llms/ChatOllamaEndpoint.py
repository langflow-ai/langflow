from typing import Optional, List
from langchain.chat_models.base import BaseChatModel
from langchain_community.chat_models import ChatOllama
from langflow import CustomComponent
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler


class ChatOllamaComponent(CustomComponent):
    display_name = "ChatOllama"
    description = "Local LLM for chat with Ollama."

    def build_config(self) -> dict:
        return {
            "base_url": {
                "display_name": "Base URL",
                "value": "http://localhost:11434",
                "info": "Endpoint of the Ollama API."
            },
            "model": {
                "display_name": "Model Name",
                "value": "llama2",
                "info": "Refer to https://ollama.ai/library for more models."
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "value": 0.8,
                "info": "Controls the creativity of model responses."
            },
            "cache": {
                "display_name": "Cache",
                "field_type": "bool",
                "info": "Enable or disable caching.",
                "advanced": True,
                "value": False
            },
            "callback_manager": {
                "display_name": "Callback Manager",
                "info": "Optional callback manager for additional functionality.",
                "advanced": True,
                "value": None
            },
            "callbacks": {
                "display_name": "Callbacks",
                "info": "Callbacks to execute during model runtime.",
                "advanced": True,
                "value": None
            },
            "format": {
                "display_name": "Format",
                "field_type": "str",
                "info": "Specify the format of the output (e.g., json).",
                "advanced": True,
                "value": None
            },
            "metadata": {
                "display_name": "Metadata",
                "info": "Metadata to add to the run trace.",
                "advanced": True,
                "value": None
            },
            "mirostat": {
                "display_name": "Mirostat",
                "field_type": "int",
                "info": "Enable Mirostat sampling for controlling perplexity. (default: 0, 0 = disabled, 1 = Mirostat, 2 = Mirostat 2.0)",
                "advanced": True,
                "value": 0
            },
            "mirostat_eta": {
                "display_name": "Mirostat Eta",
                "field_type": "float",
                "info": "Learning rate for Mirostat algorithm. (Default: 0.1)",
                "advanced": True,
                "value": 0.1
            },
            "mirostat_tau": {
                "display_name": "Mirostat Tau",
                "field_type": "float",
                "info": "Controls the balance between coherence and diversity of the output. (Default: 5.0)",
                "advanced": True,
                "value": 5.0
            },
            "num_ctx": {
                "display_name": "Context Window Size",
                "field_type": "int",
                "info": "Size of the context window for generating tokens. (Default: 2048)",
                "advanced": True,
                "value": 2048
            },
            "num_gpu": {
                "display_name": "Number of GPUs",
                "field_type": "int",
                "info": "Number of GPUs to use for computation. (Default: 1 on macOS, 0 to disable)",
                "advanced": True,
                "value": 0
            },
            "num_thread": {
                "display_name": "Number of Threads",
                "field_type": "int",
                "info": "Number of threads to use during computation. (Default: detected for optimal performance)",
                "advanced": True,
                "value": None
            },
            "repeat_last_n": {
                "display_name": "Repeat Last N",
                "field_type": "int",
                "info": "How far back the model looks to prevent repetition. (Default: 64, 0 = disabled, -1 = num_ctx)",
                "advanced": True,
                "value": 64
            },
            "repeat_penalty": {
                "display_name": "Repeat Penalty",
                "field_type": "float",
                "info": "Penalty for repetitions in generated text. (Default: 1.1)",
                "advanced": True,
                "value": 1.1
            },
            "tfs_z": {
                "display_name": "TFS Z",
                "field_type": "float",
                "info": "Tail free sampling value. (Default: 1)",
                "advanced": True,
                "value": 1.0
            },
            "timeout": {
                "display_name": "Timeout",
                "field_type": "int",
                "info": "Timeout for the request stream.",
                "advanced": True,
                "value": None
            },
            "top_k": {
                "display_name": "Top K",
                "field_type": "int",
                "info": "Limits token selection to top K. (Default: 40)",
                "advanced": True,
                "value": 40
            },
            "top_p": {
                "display_name": "Top P",
                "field_type": "float",
                "info": "Works together with top-k. (Default: 0.9)",
                "advanced": True,
                "value": 0.9
            },
            "verbose": {
                "display_name": "Verbose",
                "field_type": "bool",
                "info": "Whether to print out response text.",
                "value": None
            },
            "tags": {
                "display_name": "Tags",
                "field_type": "list",
                "info": "Tags to add to the run trace.",
                "advanced": True,
                "value": None
            },
        }

    def build(self, base_url: str, model: str, mirostat: Optional[int],
              mirostat_eta: Optional[float], mirostat_tau: Optional[float],
              num_ctx: Optional[int], num_gpu: Optional[int],
              repeat_last_n: Optional[int],
              repeat_penalty: Optional[float], temperature: Optional[float],
              tfs_z: Optional[float],
              num_thread: Optional[int] = None,
              stop: Optional[List[str]] = None,
              tags: Optional[List[str]] = None,
              system: Optional[str] = None,
              template: Optional[str] = None,
              timeout: Optional[int] = None,
              top_k: Optional[int] = None,
              top_p: Optional[int] = None, verbose: Optional[bool] = None
              ) -> BaseChatModel:

        callback_manager = CallbackManager(
            [StreamingStdOutCallbackHandler()])

        llm_params = {
            "base_url": base_url,
            "model": model,
            "mirostat": mirostat,
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
            "callback_manager": callback_manager
        }

        # None Value Remove
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            output = ChatOllama(**llm_params)
        except Exception as e:
            raise ValueError("Could not initialize Ollama LLM.") from e

        return output
