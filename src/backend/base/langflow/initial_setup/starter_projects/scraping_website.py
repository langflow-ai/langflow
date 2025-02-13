from langflow.components.inputs import SecretStrInput, TextInput
from langflow.components.outputs import TextOutput
from langflow.components.scrapegraph import ScrapeGraphSmartScraperApi
from langflow.graph import Graph


def scraping_website_graph():
    # Create components
    text_input = TextInput()
    api_key_input = SecretStrInput()
    prompt_input = TextInput()
    scraper = ScrapeGraphSmartScraperApi()
    text_output = TextOutput()

    # Set up connections
    scraper.set(url=text_input.text_value, api_key=api_key_input.value, prompt=prompt_input.text_value)
    text_output.set(input_value=scraper.data)

    return Graph(text_input, prompt_input, api_key_input, text_output)
