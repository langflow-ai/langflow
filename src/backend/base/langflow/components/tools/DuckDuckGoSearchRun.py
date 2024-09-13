from langflow.base.io.text import TextComponent
from langflow.io import StrInput, IntInput, Output
from langflow.schema.message import Message
from langchain_community.tools import DuckDuckGoSearchRun
import time
from typing import Optional


class DuckDuckGoSearchComponent(TextComponent):
    display_name = "DuckDuckGo Search"
    description = "Perform web searches using the DuckDuckGo search engine with retry logic."
    icon = "DuckDuckGo"
    name = "DuckDuckGoSearch"

    inputs = [
        StrInput(
            name="query",
            display_name="Search Query",
            required=True,
            info="The search query to be executed.",
        ),
        IntInput(
            name="num_results",
            display_name="Number of Results",
            value=5,
            info="The number of search results to return (default: 5).",
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            value=3,
            info="Maximum number of retry attempts for rate-limited requests.",
            advanced=True,
        ),
        IntInput(
            name="initial_delay",
            display_name="Initial Retry Delay",
            value=5,
            info="Initial delay (in seconds) between retry attempts.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Search Results", name="search_results", method="search_response"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._code: Optional[str] = kwargs.get("_code")
        self.search_tool = DuckDuckGoSearchRun()

    def execute_search(self, query: str) -> str:
        return self.search_tool.run(f"{query} (site:*)")

    def format_results(self, results: str, num_results: int) -> str:
        result_list = results.split("\n")[:num_results]
        return "\n\n".join([f"{i+1}. {result}" for i, result in enumerate(result_list)])

    def search_with_retry(self, query: str, max_retries: int, initial_delay: int) -> str:
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                return self.execute_search(query)
            except Exception as e:
                if "202 Ratelimit" in str(e) and attempt < max_retries - 1:
                    self.status = (
                        f"Rate limit hit. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    raise e
        raise Exception("Max retries reached. Unable to complete the search.")

    def search_response(self) -> Message:
        try:
            results = self.search_with_retry(self.query, self.max_retries, self.initial_delay)
            formatted_results = self.format_results(results, self.num_results)
            message_content = f"Search results for '{self.query}':\n\n{formatted_results}"
            self.status = "Search completed successfully."
            return Message(text=message_content)
        except Exception as e:
            error_message = f"An error occurred during the search: {str(e)}"
            self.status = error_message
            return Message(content=error_message)
