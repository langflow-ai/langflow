import requests

from langflow.custom import Component
from langflow.io import BoolInput, IntInput, MessageTextInput, Output, SecretStrInput
from langflow.schema import Data, DataFrame


class SlackConversationsHistoryComponent(Component):
    display_name = "Fetch Slack Messages"
    description = "Fetches a conversation's history of messages and events."
    icon = "SlackDirectoryLoader"
    name = "SlackConversationsHistoryComponent"

    inputs = [
        MessageTextInput(
            name="channel",
            display_name="Channel",
            info="Conversation ID to fetch history for.",
            required=True,
        ),
        SecretStrInput(
            name="token",
            display_name="Token",
            info="Authentication token bearing required scopes.",
            required=True,
        ),
        MessageTextInput(
            name="cursor",
            display_name="Cursor",
            info="Paginate through collections of data by setting the cursor parameter to a next_cursor attribute returned by a previous request's response_metadata.",
            advanced=True,
            value="",
        ),
        BoolInput(
            name="include_all_metadata",
            display_name="Include all metadata",
            info="Return all metadata associated with this message.",
            advanced=True,
            value=False,
        ),
        BoolInput(
            name="inclusive",
            display_name="Inclusive",
            info="Include messages with oldest or latest timestamps in results. Ignored unless either timestamp is specified.",
            advanced=True,
            value=False,
        ),
        MessageTextInput(
            name="latest",
            display_name="Latest Timestamp",
            info="Only messages before this Unix timestamp will be included in results.",
            advanced=True,
            value="",
        ),
        MessageTextInput(
            name="oldest",
            display_name="Oldest Timestamp",
            info="Only messages after this Unix timestamp will be included in results.",
            advanced=True,
            value="",
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="The maximum number of items to return. Maximum of 999.",
            advanced=True,
            value=100,
        ),
    ]

    outputs = [
        Output(
            display_name="Slack Response",
            name="response",
            method="build_slack_response",
        ),
        Output(display_name="Messages", name="messages", method="build_messages"),
    ]

    def fetch_messages(self) -> list[dict]:
        """Retrive messages using [conversations.history](https://api.slack.com/methods/conversations.history) from Slack API.
        """
        url = "https://slack.com/api/conversations.history"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        payload = {
            "channel": self.channel,
            "cursor": self.cursor,
            "include_all_metadata": self.include_all_metadata,
            "inclusive": self.inclusive,
            "latest": self.latest,
            "oldest": self.oldest,
            "limit": self.limit,
        }

        http_response = requests.request("POST", url, json=payload, headers=headers)
        json_response = http_response.json()

        if not json_response.get("ok"):
            error_message = json_response.get("error")
            raise ValueError(f"Slack Error: {error_message}")

        return json_response

    def build_slack_response(self) -> Data:
        """Build the output object containing the Slack API response.
        """
        data = Data(
            data=self.fetch_messages(),
            text_key="messages",
            default_value="No content available",
        )

        return data

    def build_messages(self) -> DataFrame:
        """Build the output object containing messages returned from the Slack API.
        """
        data = [
            Data(data=message, text_key="text")
            for message in self.response.value.messages
        ]

        return DataFrame(data)
