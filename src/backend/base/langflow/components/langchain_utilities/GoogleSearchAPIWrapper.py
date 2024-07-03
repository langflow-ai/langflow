from typing import Callable, Union

from langchain_community.utilities.google_search import GoogleSearchAPIWrapper

from langflow.custom import CustomComponent


class GoogleSearchAPIWrapperComponent(CustomComponent):
    display_name = "GoogleSearchAPIWrapper"
    description = "Wrapper for Google Search API."
    name = "GoogleSearchAPIWrapper"

    def build_config(self):
        return {
            "google_api_key": {"display_name": "Google API Key", "password": True},
            "google_cse_id": {"display_name": "Google CSE ID", "password": True},
        }

    def build(
        self,
        google_api_key: str,
        google_cse_id: str,
    ) -> Union[GoogleSearchAPIWrapper, Callable]:
        return GoogleSearchAPIWrapper(google_api_key=google_api_key, google_cse_id=google_cse_id)  # type: ignore
