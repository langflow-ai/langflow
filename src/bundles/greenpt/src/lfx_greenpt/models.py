"""OpenAI-compatible LangChain models pinned to the GreenPT API."""

from typing import Any

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

GREENPT_BASE_URL = "https://api.greenpt.ai/v1"


class ChatGreenPT(ChatOpenAI):
    """ChatOpenAI configured for GreenPT's fixed API endpoint."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize a chat model pinned to GreenPT."""
        kwargs["base_url"] = GREENPT_BASE_URL
        super().__init__(**kwargs)


class GreenPTEmbeddings(OpenAIEmbeddings):
    """OpenAIEmbeddings configured for GreenPT's fixed API endpoint."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize embeddings pinned to GreenPT."""
        kwargs["base_url"] = GREENPT_BASE_URL
        super().__init__(**kwargs)
