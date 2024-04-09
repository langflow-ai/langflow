from typing import List, Optional

from langflow.field_typing import BaseLanguageModel
from langchain_community.llms.ollama import Ollama

from langflow.interface.custom.custom_component import CustomComponent


class OllamaLLM(CustomComponent):
    display_name = "Ollama"
    description = "Local LLM with Ollama."

    def build_config(self) -> dict:
        return {
            "base_url": {
                "display_name": "Base URL",
                "info": "Endpoint of the Ollama API. Defaults to 'http://localhost:11434' if not specified.",
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
                "info": "Learning rate influencing the algorithm's response to feedback.",
                "advanced": True,
            },
            "mirostat_tau": {
                "display_name": "Mirostat Tau",
                "field_type": "float",
                "info": "Controls balance between coherence and diversity.",
                "advanced": True,
            },
            "num_ctx": {
                "display_name": "Context Window Size",
                "field_type": "int",
                "info": "Size of the context window for generating the next token.",
                "advanced": True,
            },
            "num_gpu": {
                "display_name": "Number of GPUs",
                "field_type": "int",
                "info": "Number of GPUs to use for computation.",
                "advanced": True,
            },
            "num_thread": {
                "display_name": "Number of Threads",
                "field_type": "int",
                "info": "Number of threads to use during computation.",
                "advanced": True,
            },
            "repeat_last_n": {
                "display_name": "Repeat Last N",
                "field_type": "int",
                "info": "Sets how far back the model looks to prevent repetition.",
                "advanced": True,
            },
            "repeat_penalty": {
                "display_name": "Repeat Penalty",
                "field_type": "float",
                "info": "Penalty for repetitions in generated text.",
                "advanced": True,
            },
            "stop": {
                "display_name": "Stop Tokens",
                "info": "List of tokens to signal the model to stop generating text.",
                "advanced": True,
            },
            "tfs_z": {
                "display_name": "TFS Z",
                "field_type": "float",
                "info": "Tail free sampling to reduce impact of less probable tokens.",
                "advanced": True,
            },
            "top_k": {
                "display_name": "Top K",
                "field_type": "int",
                "info": "Limits token selection to top K for reducing nonsense generation.",
                "advanced": True,
            },
            "top_p": {
                "display_name": "Top P",
                "field_type": "int",
                "info": "Works with top-k to control diversity of generated text.",
                "advanced": True,
            },
        }

    def build(
        self,
        base_url: Optional[str],
        model: str,
        temperature: Optional[float],
        mirostat: Optional[str],
        mirostat_eta: Optional[float] = None,
        mirostat_tau: Optional[float] = None,
        num_ctx: Optional[int] = None,
        num_gpu: Optional[int] = None,
        num_thread: Optional[int] = None,
        repeat_last_n: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[List[str]] = None,
        tfs_z: Optional[float] = None,
        top_k: Optional[int] = None,
        top_p: Optional[int] = None,
    ) -> BaseLanguageModel:
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

        try:
            llm = Ollama(
                base_url=base_url,
                model=model,
                mirostat=mirostat_value,
                mirostat_eta=mirostat_eta,
                mirostat_tau=mirostat_tau,
                num_ctx=num_ctx,
                num_gpu=num_gpu,
                num_thread=num_thread,
                repeat_last_n=repeat_last_n,
                repeat_penalty=repeat_penalty,
                temperature=temperature,
                stop=stop,
                tfs_z=tfs_z,
                top_k=top_k,
                top_p=top_p,
            )

        except Exception as e:
            raise ValueError("Could not connect to Ollama.") from e

        return llm
