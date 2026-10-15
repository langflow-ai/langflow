from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
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
    user_path_and_params,
)


class TwittrAPIUserTweetsComponent(Component):
    """Fetch the latest posts from one X (Twitter) account."""

    display_name = "TwittrAPI User Tweets"
    description = "Get the latest posts from an X (Twitter) account, by username or numeric user ID."
    documentation = "https://www.twittrapi.com/docs/reference/user-userid-tweets"
    icon = "TwittrAPI"

    inputs = [
        MessageTextInput(
            name="user",
            display_name="Username or User ID",
            required=True,
            tool_mode=True,
            info="X handle (for example 'jack' or '@jack') or numeric user ID. Digits are read as a user ID.",
        ),
        api_key_input(),
        count_input(),
        cursor_input(),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="twittrapi_user_tweets"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            path, params = user_path_and_params(self.user, "tweets")
        except ValueError as e:
            rows = [error_data(str(e))]
            self.status = rows
            return rows
        params.update({"count": count_value(self.count), "cursor": clean(self.cursor)})
        return fetch_page(self, path, params, tweet_to_data)

    def twittrapi_user_tweets(self) -> DataFrame:
        """Return one row per post."""
        return DataFrame(self.fetch_content())
