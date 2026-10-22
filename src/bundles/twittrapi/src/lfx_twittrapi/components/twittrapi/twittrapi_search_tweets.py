from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_twittrapi.components.twittrapi._common import (
    api_key_input,
    clean,
    count_input,
    count_value,
    cursor_input,
    error_data,
    fetch_page,
    tweet_to_data,
    user_to_data,
)

CATEGORIES = ["Top", "Latest", "People", "Photos", "Videos"]


class TwittrAPISearchTweetsComponent(Component):
    """Search X (Twitter) with the same query syntax as the X search box."""

    display_name = "TwittrAPI Search Tweets"
    description = "Search X (Twitter) posts, or people, with X search operators such as from:, lang: and since:."
    documentation = "https://www.twittrapi.com/docs/reference/search"
    icon = "TwittrAPI"

    inputs = [
        MessageTextInput(
            name="search_query",
            display_name="Search Query",
            required=True,
            tool_mode=True,
            info="X search query, for example 'langflow lang:en' or 'from:jack'.",
        ),
        api_key_input(),
        DropdownInput(
            name="category",
            display_name="Category",
            options=CATEGORIES,
            value="Top",
            tool_mode=True,
            info="Search tab. People returns user profiles instead of posts.",
        ),
        count_input(),
        cursor_input(),
    ]

    outputs = [
        # The method name is also the tool name in tool mode; keep it vendor-specific
        # so it cannot collide with other search tools on the same Agent.
        Output(display_name="Table", name="dataframe", method="twittrapi_search_tweets"),
    ]

    def fetch_content(self) -> list[Data]:
        category = self.category if self.category in CATEGORIES else "Top"
        params = {
            "searchItem": clean(self.search_query),
            "category": category,
            "count": count_value(self.count),
            "cursor": clean(self.cursor),
        }
        if not params["searchItem"]:
            rows = [error_data("A search query is required.")]
            self.status = rows
            return rows
        to_data = user_to_data if category == "People" else tweet_to_data
        return fetch_page(self, "/search", params, to_data)

    def twittrapi_search_tweets(self) -> DataFrame:
        """Run the search and return one row per post (or per user for People)."""
        return DataFrame(self.fetch_content())
