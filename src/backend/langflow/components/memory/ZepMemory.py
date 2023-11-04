from typing import Optional

from langchain.memory import ZepMemory
from langchain.schema import BaseMemory

from langflow import CustomComponent


class ZepMemoryComponent(CustomComponent):
    display_name: str = "Zep Memory"
    description: str = "Use the Zep service for chat history persistence and retrieval."

    def build_config(self):
        return {
            "session_id": {"display_name": "Session ID", "field_type": "str"},
            "url": {"display_name": "URL", "field_type": "str"},
            "api_key": {
                "display_name": "API Key",
                "field_type": "password",
                "optional": True,
            },
            "output_key": {
                "display_name": "Output Key",
                "field_type": "str",
                "optional": True,
            },
            "input_key": {
                "display_name": "Input Key",
                "field_type": "str",
                "optional": True,
            },
            "return_messages": {
                "display_name": "Return Messages",
                "field_type": "bool",
                "default": False,
            },
            "human_prefix": {
                "display_name": "Human Prefix",
                "field_type": "str",
                "default": "Human",
            },
            "ai_prefix": {
                "display_name": "AI Prefix",
                "field_type": "str",
                "default": "AI",
            },
            "memory_key": {
                "display_name": "Memory Key",
                "field_type": "str",
                "default": "history",
            },
            "code": {"show": False},
        }

    def build(
        self,
        session_id: str,
        url: str,
        api_key: Optional[str] = None,
        output_key: Optional[str] = None,
        input_key: Optional[str] = None,
        return_messages: bool = False,
        human_prefix: str = "Human",
        ai_prefix: str = "AI",
        memory_key: str = "history",
    ) -> BaseMemory:
        try:
            memory = ZepMemory(
                session_id=session_id,
                url=url,
                api_key=api_key,
                output_key=output_key,
                input_key=input_key,
                return_messages=return_messages,
                human_prefix=human_prefix,
                ai_prefix=ai_prefix,
                memory_key=memory_key,
            )  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to AmazonKendra API.") from e
        return memory
