from typing import Callable, Union

from langchain_community.utilities.wolfram_alpha import WolframAlphaAPIWrapper

from langflow.custom import CustomComponent

# Since all the fields in the JSON have show=False, we will only create a basic component
# without any configurable fields.


class WolframAlphaAPIWrapperComponent(CustomComponent):
    display_name = "WolframAlphaAPIWrapper"
    description = "Wrapper for Wolfram Alpha."

    def build_config(self):
        return {"appid": {"display_name": "App ID", "type": "str", "password": True}}

    def build(self, appid: str) -> Union[Callable, WolframAlphaAPIWrapper]:
        return WolframAlphaAPIWrapper(wolfram_alpha_appid=appid)  # type: ignore
