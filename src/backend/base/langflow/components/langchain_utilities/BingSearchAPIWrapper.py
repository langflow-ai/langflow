# Assuming `BingSearchAPIWrapper` is a class that exists in the context
# and has the appropriate methods and attributes.
# We need to make sure this class is importable from the context where this code will be running.
from langchain_community.utilities.bing_search import BingSearchAPIWrapper

from langflow.custom import CustomComponent


class BingSearchAPIWrapperComponent(CustomComponent):
    display_name = "BingSearchAPIWrapper"
    description = "Wrapper for Bing Search API."

    def build_config(self):
        return {
            "bing_search_url": {"display_name": "Bing Search URL"},
            "bing_subscription_key": {
                "display_name": "Bing Subscription Key",
                "password": True,
            },
            "k": {"display_name": "Number of results", "advanced": True},
            # 'k' is not included as it is not shown (show=False)
        }

    def build(
        self,
        bing_search_url: str,
        bing_subscription_key: str,
        k: int = 10,
    ) -> BingSearchAPIWrapper:
        # 'k' has a default value and is not shown (show=False), so it is hardcoded here
        return BingSearchAPIWrapper(bing_search_url=bing_search_url, bing_subscription_key=bing_subscription_key, k=k)
