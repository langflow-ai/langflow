from langflow.custom import Component
from langflow.io import (
    MessageTextInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data


class ScrapeGraphSearchApi(Component):
    display_name: str = "ScrapeGraphSearchApi"
    description: str = """ScrapeGraph Search API.
    Given a search prompt, it will return search results using ScrapeGraph's search functionality.
    More info at https://docs.scrapegraphai.com/services/searchscraper"""
    name = "ScrapeGraphSearchApi"

    documentation: str = "https://docs.scrapegraphai.com/introduction"
    icon = "ScrapeGraph"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="ScrapeGraph API Key",
            required=True,
            password=True,
            info="The API key to use ScrapeGraph API.",
        ),
        MessageTextInput(
            name="user_prompt",
            display_name="Search Prompt",
            tool_mode=True,
            info="The search prompt to use.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="search"),
    ]

    def search(self) -> list[Data]:
        try:
            from scrapegraph_py import Client
            from scrapegraph_py.logger import sgai_logger
        except ImportError as e:
            msg = "Could not import scrapegraph-py package. Please install it with `pip install scrapegraph-py`."
            raise ImportError(msg) from e

        # Set logging level
        sgai_logger.set_logging(level="INFO")

        # Initialize the client with API key
        sgai_client = Client(api_key=self.api_key)

        try:
            # SearchScraper request
            response = sgai_client.searchscraper(
                user_prompt=self.user_prompt,
            )

            # Close the client
            sgai_client.close()

            return Data(data=response)
        except Exception:
            sgai_client.close()
            raise
