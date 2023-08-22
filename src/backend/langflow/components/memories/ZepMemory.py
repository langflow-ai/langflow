from langchain.memory.zep_memory import ZepMemory
from langflow import CustomComponent
from langchain.schema.memory import BaseMemory


class ZepMemoryComponent(CustomComponent):
    display_name: str = "Zep Memory"

    def build_config(self):
        return {
            "zep_api_url": {
                "display_name": "Zep API URL",
                "value": "http://localhost:8000",
            },
            "api_key": {
                "password": True,
                "display_name": "API Key",
            },
            "session_id": {
                "display_name": "Session ID",
                "info": "The session ID to use for the memory.",
            },
        }

    def build(
        self,
        api_key: str,
        session_id: str,
        memory_key: str,
        return_messages: bool,
        zep_api_url: str = "http://localhost:8000",
    ) -> BaseMemory:
        return ZepMemory(
            session_id=session_id,
            url=zep_api_url,
            api_key=api_key,
            memory_key=memory_key,
            return_messages=return_messages,
        )
