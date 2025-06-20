from langflow.custom.custom_component.component import Component
from langflow.io import BoolInput, DropdownInput, Output, QueryInput, SecretStrInput
from langflow.schema.data import Data
from langflow.schema.message import Message


class JigsawStackAIWebSearchComponent(Component):
    display_name = "AI Web Search"
    description = "Effortlessly search the Web and get access to high-quality results powered with AI."
    documentation = "https://jigsawstack.com/docs/api-reference/web/ai-search"
    icon = "JigsawStack"
    name = "JigsawStackAISearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        QueryInput(
            name="query",
            display_name="Query",
            info="The search value. The maximum query character length is 400",
            required=True,
            tool_mode=True,
        ),
        BoolInput(
            name="ai_overview",
            display_name="AI Overview",
            info="Include AI powered overview in the search results",
            required=False,
            value=True,
        ),
        DropdownInput(
            name="safe_search",
            display_name="Safe Search",
            info="Enable safe search to filter out adult content",
            required=False,
            options=["moderate", "strict", "off"],
            value="off",
        ),
        BoolInput(
            name="spell_check",
            display_name="Spell Check",
            info="Spell check the search query",
            required=False,
            value=True,
        ),
    ]

    outputs = [
        Output(display_name="AI Search Results", name="search_results", method="search"),
        Output(display_name="Content Text", name="content_text", method="get_content_text"),
    ]

    def search(self) -> Data:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.6"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            client = JigsawStack(api_key=self.api_key)

            # build request object
            search_params = {}
            if self.query:
                search_params["query"] = self.query
            if self.ai_overview is not None:
                search_params["ai_overview"] = self.ai_overview
            if self.safe_search:
                search_params["safe_search"] = self.safe_search
            if self.spell_check is not None:
                search_params["spell_check"] = self.spell_check

            # Call web scraping
            response = client.web.search(search_params)

            api_error_msg = "JigsawStack API returned unsuccessful response"
            if not response.get("success", False):
                raise ValueError(api_error_msg)

            # Create comprehensive data object
            result_data = {
                "query": self.query,
                "ai_overview": response.get("ai_overview", ""),
                "spell_fixed": response.get("spell_fixed", False),
                "is_safe": response.get("is_safe", True),
                "results": response.get("results", []),
                "success": True,
            }

            self.status = f"Search complete for: {response.get('query', '')}"

            return Data(data=result_data)

        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)

    def get_content_text(self) -> Message:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError:
            return Message(text="Error: JigsawStack package not found.")

        try:
            # Initialize JigsawStack client
            client = JigsawStack(api_key=self.api_key)

            search_params = {}
            if self.query:
                search_params["query"] = self.query
            if self.ai_overview is not None:
                search_params["ai_overview"] = self.ai_overview
            if self.safe_search:
                search_params["safe_search"] = self.safe_search
            if self.spell_check is not None:
                search_params["spell_check"] = self.spell_check

            # Call web scraping
            response = client.web.search(search_params)

            request_failed_msg = "Request Failed"
            if not response.get("success", False):
                raise JigsawStackError(request_failed_msg)

            # Return the content as text
            content = response.get("ai_overview", "")
            return Message(text=content)

        except JigsawStackError as e:
            return Message(text=f"Error while using AI Search: {e!s}")
