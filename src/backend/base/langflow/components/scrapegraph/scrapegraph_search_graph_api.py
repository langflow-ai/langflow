from langflow.custom import Component
from langflow.io import (
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema import Data


class ScrapeGraphSearchGraphApi(Component):
    display_name: str = "ScrapeGraphSearchGraphApi"
    description: str = """ScrapeGraph Search Graph API.
    Given a search prompt, it will search on the internet and return relevant information
    in structured format.
    More info at https://docs.scrapegraphai.com/services/searchscraper"""
    name = "ScrapeGraphSearchGraphApi"

    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.scrapegraphai.com/introduction"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="ScrapeGraph API Key",
            required=True,
            password=True,
            info="The API key to use ScrapeGraph API.",
        ),
        StrInput(
            name="user_prompt",
            display_name="Search Prompt",
            required=True,
            info="The search prompt to find relevant information.",
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
