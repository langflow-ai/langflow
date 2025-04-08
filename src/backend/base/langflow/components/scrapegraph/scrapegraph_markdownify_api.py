from langflow.custom import Component
from langflow.io import (
    MessageTextInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data


class ScrapeGraphMarkdownifyApi(Component):
    display_name: str = "ScrapeGraphMarkdownifyApi"
    description: str = """ScrapeGraph Markdownify API.
    Given a URL, it will return the markdownified content of the website.
    More info at https://docs.scrapegraphai.com/services/markdownify"""
    name = "ScrapeGraphMarkdownifyApi"

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
        MessageTextInput(
            name="url",
            display_name="URL",
            tool_mode=True,
            info="The URL to markdownify.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="scrape"),
    ]

    def scrape(self) -> list[Data]:
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
            # Markdownify request
            response = sgai_client.markdownify(
                website_url=self.url,
            )

            # Close the client
            sgai_client.close()

            return Data(data=response)
        except Exception:
            sgai_client.close()
            raise
