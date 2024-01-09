
from langflow import CustomComponent
from typing import Dict, Optional

# Assuming the existence of GoogleSerperAPIWrapper class in the serper module
# If this class does not exist, you would need to create it or import the appropriate class from another module
from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper


class GoogleSerperAPIWrapperComponent(CustomComponent):
    display_name = "GoogleSerperAPIWrapper"
    description = "Wrapper around the Serper.dev Google Search API."

    def build_config(self) -> Dict[str, Dict]:
        return {
            "result_key_for_type": {
                "display_name": "Result Key for Type",
                "show": True,
                "multiline": False,
                "password": False,  # corrected based on error message
                "name": "result_key_for_type",
                "advanced": False,
                "dynamic": False,
                "info": '',
                "field_type": "dict",
                "list": False,
                "value": {
                    "news": "news",
                    "places": "places",
                    "images": "images",
                    "search": "organic"
                }
            },
            "serper_api_key": {
                "display_name": "Serper API Key",
                "show": True,
                "multiline": False,
                "password": False,  # corrected based on error message
                "name": "serper_api_key",
                "advanced": False,
                "dynamic": False,
                "info": '',
                "type": "str",
                "list": False,
                "value": ""  # assuming empty string as default, needs to be set by user
            }
        }

    def build(
        self,
        result_key_for_type: Optional[Dict[str, str]] = None,
        serper_api_key: Optional[str] = None,
    ) -> GoogleSerperAPIWrapper:
        return GoogleSerperAPIWrapper(
            result_key_for_type=result_key_for_type,
            serper_api_key=serper_api_key
        )
