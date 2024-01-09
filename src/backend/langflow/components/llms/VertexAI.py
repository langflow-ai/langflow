
from langflow import CustomComponent
from langchain.llms import BaseLLM
from typing import Optional, Union, Callable, Dict

class VertexAIComponent(CustomComponent):
    display_name = "VertexAI"
    description = "Google Vertex AI large language models"

    def build_config(self):
        return {
            "credentials": {
                "display_name": "Credentials",
                "type": "file",
                "file_types": ["json"],
                "required": False,
                "default": None,
            },
            "location": {
                "display_name": "Location",
                "type": "str",
                "default": "us-central1",
                "required": False,
            },
            "max_output_tokens": {
                "display_name": "Max Output Tokens",
                "type": "int",
                "default": 128,
                "required": False,
            },
            "max_retries": {
                "display_name": "Max Retries",
                "type": "int",
                "default": 6,
                "required": False,
            },
            "metadata": {
                "display_name": "Metadata",
                "type": "dict",
                "required": False,
                "default": {},
            },
            "model_name": {
                "display_name": "Model Name",
                "type": "str",
                "default": "text-bison",
                "required": False,
            },
            "n": {
                "display_name": "N",
                "type": "int",
                "default": 1,
                "required": False,
            },
            "project": {
                "display_name": "Project",
                "type": "str",
                "required": False,
                "default": None,
            },
            "request_parallelism": {
                "display_name": "Request Parallelism",
                "type": "int",
                "default": 5,
                "required": False,
            },
            "streaming": {
                "display_name": "Streaming",
                "type": "bool",
                "default": False,
                "required": False,
            },
            "temperature": {
                "display_name": "Temperature",
                "type": "float",
                "default": 0.0,
                "required": False,
            },
            "top_k": {
                "display_name": "Top K",
                "type": "int",
                "default": 40,
                "required": False,
            },
            "top_p": {
                "display_name": "Top P",
                "type": "float",
                "default": 0.95,
                "required": False,
            },
            "tuned_model_name": {
                "display_name": "Tuned Model Name",
                "type": "str",
                "required": False,
                "default": None,
            },
            "verbose": {
                "display_name": "Verbose",
                "type": "bool",
                "default": False,
                "required": False,
            },
        }

    def build(
        self,
        credentials: Optional[str] = None,
        location: str = "us-central1",
        max_output_tokens: int = 128,
        max_retries: int = 6,
        metadata: Dict = None,
        model_name: str = "text-bison",
        n: int = 1,
        project: Optional[str] = None,
        request_parallelism: int = 5,
        streaming: bool = False,
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
        tuned_model_name: Optional[str] = None,
        verbose: bool = False,
    ) -> Union[BaseLLM, Callable]:
        if metadata is None:
            metadata = {}

        # Import the appropriate VertexAI class from the langchain.llms module
        from langchain.llms import VertexAI

        return VertexAI(
            credentials=credentials,
            location=location,
            max_output_tokens=max_output_tokens,
            max_retries=max_retries,
            metadata=metadata,
            model_name=model_name,
            n=n,
            project=project,
            request_parallelism=request_parallelism,
            streaming=streaming,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            tuned_model_name=tuned_model_name,
            verbose=verbose,
        )
