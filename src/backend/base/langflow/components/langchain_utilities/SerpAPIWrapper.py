from typing import Callable, Union

from langchain_community.utilities.serpapi import SerpAPIWrapper

from langflow.custom import CustomComponent


class SerpAPIWrapperComponent(CustomComponent):
    display_name = "SerpAPIWrapper"
    description = "Wrapper around SerpAPI"

    def build_config(self):
        return {
            "serpapi_api_key": {"display_name": "SerpAPI API Key", "type": "str", "password": True},
            "params": {
                "display_name": "Parameters",
                "type": "dict",
                "advanced": True,
                "multiline": True,
                "value": '{"engine": "google","google_domain": "google.com","gl": "us","hl": "en"}',
            },
        }

    def build(
        self,
        serpapi_api_key: str,
        params: dict,
    ) -> Union[SerpAPIWrapper, Callable]:  # Removed quotes around SerpAPIWrapper
        return SerpAPIWrapper(  # type: ignore
            serpapi_api_key=serpapi_api_key,
            params=params,
        )
