from langchain_core.tools import tool

from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import IntInput, MessageTextInput, Output, SecretStrInput


class SeltzSearchToolkit(Component):
    display_name = "Seltz Search"
    description = (
        "Fast, up-to-date web knowledge with sources for real-time AI reasoning. "
        "Provides context-engineered web content via the Seltz Web Knowledge API."
    )
    documentation = "https://docs.seltz.ai"
    beta = True
    name = "SeltzSearch"
    icon = "Seltz"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Seltz API Key",
            password=True,
            info="Your Seltz API key. Get one at https://console.seltz.ai",
        ),
        IntInput(
            name="max_documents",
            display_name="Max Documents",
            value=10,
            info="Maximum number of documents to return per search.",
        ),
        MessageTextInput(
            name="context",
            display_name="Search Context",
            value="",
            info="Additional context to improve search quality (e.g. 'user is looking for Python documentation').",
            advanced=True,
        ),
        MessageTextInput(
            name="profile",
            display_name="Search Profile",
            value="",
            info="Search profile to use. Different profiles may use different ranking algorithms or data sources.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]

    def build_toolkit(self) -> list[Tool]:
        try:
            from seltz import Includes, Seltz, SeltzAuthenticationError, SeltzConnectionError, SeltzRateLimitError
        except ImportError as e:
            msg = "Could not import seltz package. Install it with `pip install seltz`."
            raise ImportError(msg) from e

        client = Seltz(api_key=self.api_key)
        includes = Includes(max_documents=self.max_documents)
        context = self.context or None
        profile = self.profile or None

        @tool
        def seltz_search(query: str) -> list[dict]:
            """Search the web using Seltz for up-to-date, context-engineered web content with sources.

            Returns a list of documents, each with a URL and content.
            """
            try:
                response = client.search(query, includes=includes, context=context, profile=profile)
            except SeltzAuthenticationError as e:
                msg = f"Seltz authentication failed. Check your API key: {e}"
                raise RuntimeError(msg) from e
            except SeltzRateLimitError as e:
                msg = f"Seltz rate limit exceeded. Try again later: {e}"
                raise RuntimeError(msg) from e
            except SeltzConnectionError as e:
                msg = f"Failed to connect to Seltz API: {e}"
                raise RuntimeError(msg) from e
            except Exception as e:
                msg = f"Seltz search failed: {e}"
                raise RuntimeError(msg) from e
            return [{"url": doc.url, "content": doc.content} for doc in response.documents]

        return [seltz_search]
