from typing import Optional, List

from langchain.llms import Ollama
from langchain.llms.base import BaseLLM

from langflow import CustomComponent


class OllamaLLM(CustomComponent):
    display_name = "Ollama"
    description = "Local LLM with Ollama."

    def build_config(self) -> dict:
        return {
            "base_url": {
                "display_name": "Base URL",
                "info": "Endpoint of the Ollama API. Defaults to 'http://localhost:11434' if not specified."
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

            "mirostat": {
                "display_name": "Mirostat",
                "options": ["Disabled", "Mirostat", "Mirostat 2.0"],
                "info": "Enable/disable Mirostat sampling for controlling perplexity.",
                "value": "Disabled",
                "advanced": True
            },
            "mirostat_eta": {
                "display_name": "Mirostat Eta",
                "field_type": "float",
                "info": "Learning rate influencing the algorithm's response to feedback.",
                "advanced": True
            },


            "mirostat_tau": {
                "display_name": "Mirostat Tau",
                "field_type": "float",
                "value": 5.0,
                "info": "Controls balance between coherence and diversity.",
                "advanced": True
            },
            "num_ctx": {
                "display_name": "Context Window Size",
                "field_type": "int",
                "value": 2048,
                "info": "Size of the context window for generating the next token.",
                "advanced": True
            },
            "num_gpu": {
                "display_name": "Number of GPUs",
                "field_type": "int",
                "info": "Number of GPUs to use for computation.",
                "advanced": True
            },
            "num_thread": {
                "display_name": "Number of Threads",
                "field_type": "int",
                "info": "Number of threads to use during computation.",
                "advanced": True
            },
            "repeat_last_n": {
                "display_name": "Repeat Last N",
                "field_type": "int",
                "value": 64,
                "info": "Sets how far back the model looks to prevent repetition.",
                "advanced": True
            },
            "repeat_penalty": {
                "display_name": "Repeat Penalty",
                "field_type": "float",
                "value": 1.1,
                "info": "Penalty for repetitions in generated text.",
                "advanced": True
            },

            "stop": {
                "display_name": "Stop Tokens",

                "info": "List of tokens to signal the model to stop generating text.",
                "advanced": True
            },
            "tfs_z": {
                "display_name": "TFS Z",
                "field_type": "float",
                "value": 1,
                "info": "Tail free sampling to reduce impact of less probable tokens.",
                "advanced": True
            },
            "top_k": {
                "display_name": "Top K",
                "field_type": "int",
                "value": 40,
                "info": "Limits token selection to top K for reducing nonsense generation.",
                "advanced": True
            },
            "top_p": {
                "display_name": "Top P",
                "field_type": "int",
                "value": 0.9,
                "info": "Works with top-k to control diversity of generated text.",
                "advanced": True
            },
        }

    def build(self, base_url: Optional[str], model: str, mirostat: str, mirostat_eta: Optional[float],
              mirostat_tau: Optional[float], num_ctx: Optional[int], num_gpu: Optional[int],
              num_thread: Optional[int], repeat_last_n: Optional[int], repeat_penalty: Optional[float],
              temperature: Optional[float], stop: Optional[List[str]], tfs_z: Optional[float],
              top_k: Optional[int], top_p: Optional[int]) -> BaseLLM:

        if not base_url:
            base_url = "http://localhost:11434"

        mirostat_value = 0  # Default value for 'Disabled'

        # Map the textual option to the corresponding integer
        if mirostat == "Mirostat":
            mirostat_value = 1
        elif mirostat == "Mirostat 2.0":
            mirostat_value = 2

        params = {k: v for k, v in {
            'base_url': base_url,
            'model': model,
            'mirostat': mirostat_value,
            'mirostat_eta': mirostat_eta,
            'mirostat_tau': mirostat_tau,
            'num_ctx': num_ctx,
            'num_gpu': num_gpu,
            'num_thread': num_thread,
            'repeat_last_n': repeat_last_n,
            'repeat_penalty': repeat_penalty,
            'temperature': temperature,
            'stop': stop,
            'tfs_z': tfs_z,
            'top_k': top_k,
            'top_p': top_p,
            'streaming' :"True"
        }.items() if v is not None}

        try:
            llm = Ollama(**params)
        except Exception as e:
            raise ValueError("Could not connect to Ollama.") from e

        return llm
