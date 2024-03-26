from typing import Dict

# Assuming the existence of GoogleSerperAPIWrapper class in the serper module
# If this class does not exist, you would need to create it or import the appropriate class from another module
from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper

from langflow.interface.custom.custom_component import CustomComponent


class GoogleSerperAPIWrapperComponent(CustomComponent):
    display_name = "GoogleSerperAPIWrapper"
    description = "Wrapper around the Serper.dev Google Search API."

    def build_config(self) -> Dict[str, Dict]:
        return {
            "result_key_for_type": {
                "display_name": "Result Key for Type",
                "show": True,
                "multiline": False,
                "password": False,
                "advanced": False,
                "dynamic": False,
                "info": "",
                "field_type": "dict",
                "list": False,
                "value": {
                    "news": "news",
                    "places": "places",
                    "images": "images",
                    "search": "organic",
                },
            },
            "serper_api_key": {
                "display_name": "Serper API Key",
                "show": True,
                "multiline": False,
                "password": True,
                "advanced": False,
                "dynamic": False,
                "info": "",
                "type": "str",
                "list": False,
            },
        }

    def build(
        self,
        serper_api_key: str,
    ) -> GoogleSerperAPIWrapper:
        return GoogleSerperAPIWrapper(serper_api_key=serper_api_key)
