from typing import Optional, cast

from langchain_community.chat_message_histories.zep import SearchScope, SearchType, ZepChatMessageHistory

from langflow.base.memory.memory import BaseMemoryComponent
from langflow.field_typing import Text
from langflow.schema.schema import Record


class ZepMessageReaderComponent(BaseMemoryComponent):
    display_name = "Zep Message Reader"
    description = "Retrieves stored chat messages from Zep."

    def build_config(self):
        return {
            "session_id": {
                "display_name": "Session ID",
                "info": "Session ID of the chat history.",
                "input_types": ["Text"],
            },
            "url": {
                "display_name": "Zep URL",
                "info": "URL of the Zep instance.",
                "input_types": ["Text"],
            },
            "api_key": {
                "display_name": "Zep API Key",
                "info": "API Key for the Zep instance.",
                "password": True,
            },
            "query": {
                "display_name": "Query",
                "info": "Query to search for in the chat history.",
            },
            "metadata": {
                "display_name": "Metadata",
                "info": "Optional metadata to attach to the message.",
                "advanced": True,
            },
            "search_scope": {
                "options": ["Messages", "Summary"],
                "display_name": "Search Scope",
                "info": "Scope of the search.",
                "advanced": True,
            },
            "search_type": {
                "options": ["Similarity", "MMR"],
                "display_name": "Search Type",
                "info": "Type of search.",
                "advanced": True,
            },
            "limit": {
                "display_name": "Limit",
                "info": "Limit of search results.",
                "advanced": True,
            },
            "api_base_path": {
                "display_name": "API Base Path",
                "options": ["api/v1", "api/v2"],
            },
        }

    def get_messages(self, **kwargs) -> list[Record]:
        """
        Retrieves messages from the ZepChatMessageHistory memory.

        If a query is provided, the search method is used to search for messages in the memory, otherwise all messages are returned.

        Args:
            memory (ZepChatMessageHistory): The ZepChatMessageHistory instance to retrieve messages from.
            query (str, optional): The query string to search for messages. Defaults to None.
            metadata (dict, optional): Additional metadata to filter the search results. Defaults to None.
            search_scope (str, optional): The scope of the search. Can be 'messages' or 'summary'. Defaults to 'messages'.
            search_type (str, optional): The type of search. Can be 'similarity' or 'exact'. Defaults to 'similarity'.
            limit (int, optional): The maximum number of search results to return. Defaults to None.

        Returns:
            list[Record]: A list of Record objects representing the search results.
        """
        memory: ZepChatMessageHistory = cast(ZepChatMessageHistory, kwargs.get("memory"))
        if not memory:
            raise ValueError("ZepChatMessageHistory instance is required.")
        query = kwargs.get("query")
        search_scope = kwargs.get("search_scope", SearchScope.messages).lower()
        search_type = kwargs.get("search_type", SearchType.similarity).lower()
        limit = kwargs.get("limit")

        if query:
            memory_search_results = memory.search(
                query,
                search_scope=search_scope,
                search_type=search_type,
                limit=limit,
            )
            # Get the messages from the search results if the search scope is messages
            result_dicts = []
            for result in memory_search_results:
                result_dict = {}
                if search_scope == SearchScope.messages:
                    result_dict["text"] = result.message
                else:
                    result_dict["text"] = result.summary
                result_dict["metadata"] = result.metadata
                result_dict["score"] = result.score
                result_dicts.append(result_dict)
            results = [Record(data=result_dict) for result_dict in result_dicts]
        else:
            messages = memory.messages
            results = [Record.from_lc_message(message) for message in messages]
        return results

    def build(
        self,
        session_id: Text,
        api_base_path: str = "api/v1",
        url: Optional[Text] = None,
        api_key: Optional[Text] = None,
        query: Optional[Text] = None,
        search_scope: SearchScope = SearchScope.messages,
        search_type: SearchType = SearchType.similarity,
        limit: Optional[int] = None,
    ) -> list[Record]:
        try:
            from zep_python import ZepClient
            from zep_python.langchain import ZepChatMessageHistory

            # Monkeypatch API_BASE_PATH to
            # avoid 404
            # This is a workaround for the local Zep instance
            # cloud Zep works with v2
            import zep_python.zep_client

            zep_python.zep_client.API_BASE_PATH = api_base_path
        except ImportError:
            raise ImportError(
                "Could not import zep-python package. " "Please install it with `pip install zep-python`."
            )
        if url == "":
            url = None

        zep_client = ZepClient(api_url=url, api_key=api_key)
        memory = ZepChatMessageHistory(session_id=session_id, zep_client=zep_client)
        records = self.get_messages(
            memory=memory,
            query=query,
            search_scope=search_scope,
            search_type=search_type,
            limit=limit,
        )
        self.status = records
        return records
