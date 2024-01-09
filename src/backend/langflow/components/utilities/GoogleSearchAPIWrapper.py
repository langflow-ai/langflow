
from langflow import CustomComponent
from typing import Optional, Union, Callable

# Assuming GoogleSearchAPIWrapper is a valid import based on JSON
# and it exists in some module that should be imported here.
# The import path should be replaced with the correct one once available.
from langchain_community.utilities.google_search import GoogleSearchAPIWrapper


class GoogleSearchAPIWrapperComponent(CustomComponent):
    display_name = "GoogleSearchAPIWrapper"
    description = "Wrapper for Google Search API."

    def build_config(self):
        return {
            "google_api_key": {"display_name": "Google API Key", "password": True},
            "google_cse_id": {"display_name": "Google CSE ID","password":True},
            # Fields with "show": False are omitted based on the rules
        }

    def build(
        self,
        google_api_key: Optional[str] = None,
        google_cse_id: Optional[str] = None,
    ) -> Union[GoogleSearchAPIWrapper, Callable]:
        return GoogleSearchAPIWrapper(google_api_key=google_api_key, google_cse_id=google_cse_id)
