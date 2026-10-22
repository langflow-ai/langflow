from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output
from lfx_twittrapi.components.twittrapi._common import (
    LIST_ID_PATTERN,
    api_key_input,
    clean,
    count_input,
    count_value,
    cursor_input,
    error_data,
    fetch_page,
    require_digits,
    tweet_to_data,
)


class TwittrAPIListTweetsComponent(Component):
    """Fetch the timeline of an X (Twitter) list."""

    display_name = "TwittrAPI List Tweets"
    description = "Get the latest posts from an X (Twitter) list by its numeric list ID."
    documentation = "https://www.twittrapi.com/docs/reference/lists-tweets"
    icon = "TwittrAPI"

    inputs = [
        MessageTextInput(
            name="list_id",
            display_name="List ID",
            required=True,
            tool_mode=True,
            info="Numeric list ID, the number in the list URL (x.com/i/lists/<list ID>).",
        ),
        api_key_input(),
        count_input(),
        cursor_input(),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="twittrapi_list_tweets"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            list_id = require_digits(self.list_id, LIST_ID_PATTERN, "List ID")
        except ValueError as e:
            rows = [error_data(str(e))]
            self.status = rows
            return rows
        params = {"listId": list_id, "count": count_value(self.count), "cursor": clean(self.cursor)}
        return fetch_page(self, "/lists/tweets", params, tweet_to_data)

    def twittrapi_list_tweets(self) -> DataFrame:
        """Return one row per post."""
        return DataFrame(self.fetch_content())
