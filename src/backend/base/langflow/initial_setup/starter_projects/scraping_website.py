from langflow.components.inputs import TextInput, SecretStrInput
from langflow.components.outputs import TextOutput
from langflow.components.scrapegraph import ScrapeGraphSmartScraperApi
from langflow.graph import Graph


def scraping_website_graph():
    # Create components
    text_input = TextInput()
    api_key_input = SecretStrInput()
    scraper = ScrapeGraphSmartScraperApi()
    text_output = TextOutput()

    # Set up connections
    scraper.set(url=text_input.text_value, api_key=api_key_input.value)
    text_output.set(input_value=scraper.data)

    return Graph(text_input, text_output)
