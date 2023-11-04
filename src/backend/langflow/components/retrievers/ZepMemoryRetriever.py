from typing import Optional

from langchain.retrievers import ZepRetriever
from langchain.retrievers.zep import SearchScope, SearchType
from langchain.schema import BaseRetriever

from langflow import CustomComponent


class ZepMemoryComponent(CustomComponent):
    display_name: str = "ZepMemoryRetriever"
    description: str = (
        "Retrieve summaries or messages from chat histories stored in Zep."
    )

    def build_config(self):
        return {
            "session_id": {
                "display_name": "Session ID",
                "required": True,
            },
            "url": {
                "display_name": "Server URL",
                "required": True,
            },
            "api_key": {
                "display_name": "API Key",
                "password": True,
            },
            "top_k": {
                "display_name": "Top K",
            },
            "search_scope": {
                "display_name": "Search Scope",
                "options": ["summary", "messages"],
                "field_type": "str",
            },
            "search_type": {
                "display_name": "Search Type",
                "options": ["mmr", "similarity"],
                "field_type": "str",
            },
            "mmr_lambda": {
                "display_name": "MMR Lambda",
                "optional": True,
            },
            "code": {"show": False},
        }

    def build(
        self,
        session_id: str,
        url: str,
        search_scope: str = "summary",
        search_type: str = "mmr",
        api_key: Optional[str] = None,
        top_k: Optional[int] = 3,
        mmr_lambda: Optional[float] = 0.5,
    ) -> BaseRetriever:
        try:
            memory = ZepRetriever(
                session_id=session_id,
                url=url,
                api_key=api_key,
                top_k=top_k,
                search_scope=SearchScope(search_scope),
                search_type=SearchType(search_type),
                mmr_lambda=mmr_lambda,
            )  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to the Zep API.") from e
        return memory
