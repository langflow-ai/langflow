
from langflow import CustomComponent
from typing import Callable, Union

# Assuming SerpAPIWrapper is a predefined class within the langflow context.
# If it's not, it must be defined or imported from the appropriate module.

class SerpAPIWrapperComponent(CustomComponent):
    display_name = "SerpAPIWrapper"
    description = "Wrapper around SerpAPI"

    def build_config(self):
        return {
            "serpapi_api_key": {"display_name": "SerpAPI API Key", "type": "password"},
        }

    def build(
        self,
        serpapi_api_key: str,
    ) -> Union['SerpAPIWrapper', Callable]:
        # Default parameters as defined in the JSON template.
        default_params = {
            "engine": "google",
            "google_domain": "google.com",
            "gl": "us",
            "hl": "en"
        }

        return SerpAPIWrapper(
            serpapi_api_key=serpapi_api_key,
            params=default_params
        )
