from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import (
    BoolInput,
    DropdownInput,
    IntInput,
    LinkInput,
    MessageTextInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema.message import Message


class SlackAPIComponent(LCToolComponent):
    display_name: str = "Slack"
    description: str = "Slack API"
    name = "SlackAPI"
    icon = "Slack"
    documentation: str = "https://docs.composio.dev"

    _display_to_enum_map = {
        # "Add reaction to message": "SLACK_ADD_REACTION_TO_AN_ITEM", # Disabled temporarily
        "List users endpoint": "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION",
        "List conversations endpoint": "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS",
        "Update slack chat message attributes": "SLACK_UPDATES_A_SLACK_MESSAGE",
        "Post message to channel": "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL",
        "Search messages endpoint": "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY",
        # "Retrieve conversation history": "SLACK_FETCH_CONVERSATION_HISTORY", # Disabled temporarily
        # "Remove reactions from message": "SLACK_REMOVE_REACTION_FROM_ITEM", # Disabled temporarily
        "Schedule message in chat": "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME",
        "Add reminder for user": "SLACK_CREATE_A_REMINDER",
    }

    _actions_data: dict = {
        "SLACK_ADD_REACTION_TO_AN_ITEM": {
            "display_name": "Add reaction to message",
            "parameters": [
                "SLACK_ADD_REACTION_TO_AN_ITEM-channel",
                "SLACK_ADD_REACTION_TO_AN_ITEM-name",
                "SLACK_ADD_REACTION_TO_AN_ITEM-timestamp",
            ],
        },
        "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION": {
            "display_name": "List users endpoint",
            "parameters": [
                "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-limit",
                "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-cursor",
                "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-include_locale",
            ],
        },
        "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS": {
            "display_name": "List conversations endpoint",
            "parameters": [
                "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-exclude_archived",
                "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-types",
                "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-limit",
                "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-cursor",
            ],
        },
        "SLACK_UPDATES_A_SLACK_MESSAGE": {
            "display_name": "Update slack chat message attributes",
            "parameters": [
                "SLACK_UPDATES_A_SLACK_MESSAGE-as_user",
                "SLACK_UPDATES_A_SLACK_MESSAGE-attachments",
                "SLACK_UPDATES_A_SLACK_MESSAGE-blocks",
                "SLACK_UPDATES_A_SLACK_MESSAGE-channel",
                "SLACK_UPDATES_A_SLACK_MESSAGE-link_names",
                "SLACK_UPDATES_A_SLACK_MESSAGE-parse",
                "SLACK_UPDATES_A_SLACK_MESSAGE-text",
                "SLACK_UPDATES_A_SLACK_MESSAGE-ts",
            ],
        },
        "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL": {
            "display_name": "Post message to channel",
            "parameters": [
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-as_user",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-attachments",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-blocks",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-channel",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-icon_emoji",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-icon_url",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-link_names",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-mrkdwn",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-parse",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-reply_broadcast",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-text",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-thread_ts",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-unfurl_links",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-unfurl_media",
                "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-username",
            ],
        },
        "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY": {
            "display_name": "Search messages endpoint",
            "parameters": [
                "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-count",
                "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-highlight",
                "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-page",
                "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-query",
                "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-sort",
                "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-sort_dir",
            ],
        },
        "SLACK_FETCH_CONVERSATION_HISTORY": {
            "display_name": "Retrieve conversation history",
            "parameters": [
                "SLACK_FETCH_CONVERSATION_HISTORY-channel",
                "SLACK_FETCH_CONVERSATION_HISTORY-latest",
                "SLACK_FETCH_CONVERSATION_HISTORY-oldest",
                "SLACK_FETCH_CONVERSATION_HISTORY-inclusive",
                "SLACK_FETCH_CONVERSATION_HISTORY-limit",
                "SLACK_FETCH_CONVERSATION_HISTORY-cursor",
            ],
        },
        "SLACK_REMOVE_REACTION_FROM_ITEM": {
            "display_name": "Remove reactions from message",
            "parameters": [
                "SLACK_REMOVE_REACTION_FROM_ITEM-channel",
                "SLACK_REMOVE_REACTION_FROM_ITEM-file",
                "SLACK_REMOVE_REACTION_FROM_ITEM-file_comment",
                "SLACK_REMOVE_REACTION_FROM_ITEM-name",
                "SLACK_REMOVE_REACTION_FROM_ITEM-timestamp",
            ],
        },
        "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME": {
            "display_name": "Schedule message in chat",
            "parameters": [
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-as_user",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-attachments",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-blocks",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-channel",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-link_names",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-parse",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-post_at",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-reply_broadcast",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-text",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-thread_ts",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-unfurl_links",
                "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-unfurl_media",
            ],
        },
        "SLACK_CREATE_A_REMINDER": {
            "display_name": "Add reminder for user",
            "parameters": [
                "SLACK_CREATE_A_REMINDER-text",
                "SLACK_CREATE_A_REMINDER-time",
                "SLACK_CREATE_A_REMINDER-user",
            ],
        },
    }

    _bool_variables = {
        "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-include_locale",
        "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-as_user",
        "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-link_names",
        "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-mrkdwn",
        "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-reply_broadcast",
        "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-unfurl_links",
        "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-unfurl_media",
        "SLACK_FETCH_CONVERSATION_HISTORY-inclusive",
        "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-as_user",
        "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-link_names",
        "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-reply_broadcast",
        "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-unfurl_links",
        "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-unfurl_media",
        "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-exclude_archived",
        "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-highlight",
    }

    inputs = [
        MessageTextInput(
            name="entity_id",
            display_name="Entity ID",
            value="default",
            advanced=True,
            tool_mode=True,  # Intentionally setting tool_mode=True to make this Component support both tool and non-tool functionality  # noqa: E501
        ),
        SecretStrInput(
            name="api_key",
            display_name="Composio API Key",
            required=True,
            info="Refer to https://docs.composio.dev/faq/api_key/api_key",
            real_time_refresh=True,
        ),
        LinkInput(
            name="auth_link",
            display_name="Authentication Link",
            value="",
            info="Click to authenticate with OAuth2",
            dynamic=True,
            show=False,
            placeholder="Click to authenticate",
        ),
        StrInput(
            name="auth_status",
            display_name="Auth Status",
            value="Not Connected",
            info="Current authentication status",
            dynamic=True,
            show=False,
            refresh_button=True,
        ),
        # Non tool-mode input fields
        DropdownInput(
            name="action",
            display_name="Action",
            options=[],
            value="",
            info="Select Gmail action to pass to the agent",
            show=True,
            real_time_refresh=True,
            required=True,
        ),
        IntInput(
            name="SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-limit",
            display_name="Limit",
            info="The maximum number of items to return. Fewer than the requested number of items may be returned, even if the end of the users list hasn't been reached. Providing no `limit` value will result in Slack attempting to deliver you the entire result set. If the collection is too large you may experience `limit_required` or HTTP 500 errors. ",  # noqa: E501
            show=False,
            value=1,
        ),
        MessageTextInput(
            name="SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-cursor",
            display_name="Cursor",
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first `page` of the collection. See [pagination](https://slack.dev) for more detail. ",  # noqa: E501
            show=False,
        ),
        BoolInput(
            name="SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-include_locale",
            display_name="Include Locale",
            info="Set this to `true` to receive the locale for users. Defaults to `false`",
            show=False,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-as_user",
            display_name="As User",
            info="Pass true to post the message as the authed user, instead of as a bot. Defaults to false. See [authorship](https://slack.dev) below. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. ",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-blocks",
            display_name="Blocks",
            info="A JSON-based array of structured blocks, presented as a URL-encoded string. ",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-channel",
            display_name="Channel",
            info="Channel, private group, or IM channel to send message to. Can be an encoded ID, or a name. See [below](https://slack.dev) for more details. ",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-icon_emoji",
            display_name="Icon Emoji",
            info="Emoji to use as the icon for this message. Overrides `icon_url`. Must be used in conjunction with `as_user` set to `false`, otherwise ignored. See [authorship](https://slack.dev) below. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-icon_url",
            display_name="Icon Url",
            info="URL to an image to use as the icon for this message. Must be used in conjunction with `as_user` set to false, otherwise ignored. See [authorship](https://slack.dev) below. ",  # noqa: E501
            show=False,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames.",
            show=False,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-mrkdwn",
            display_name="Mrkdwn",
            info="Disable Slack markup parsing by setting to `false`. Enabled by default.",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `none`. See [below](https://slack.dev). ",
            show=False,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-reply_broadcast",
            display_name="Reply Broadcast",
            info="Used in conjunction with `thread_ts` and indicates whether reply should be made visible to everyone in the channel or conversation. Defaults to `false`. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-text",
            display_name="Text",
            info="How this field works and whether it is required depends on other fields you use in your API call. [See below](https://slack.dev) for more detail. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-thread_ts",
            display_name="Thread Ts",
            info="Provide another message's `ts` value to make this message a reply. Avoid using a reply's `ts` value; use its parent instead. ",  # noqa: E501
            show=False,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-unfurl_links",
            display_name="Unfurl Links",
            info="Pass true to enable unfurling of primarily text-based content.",
            show=False,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-unfurl_media",
            display_name="Unfurl Media",
            info="Pass false to disable unfurling of media content.",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-username",
            display_name="Username",
            info="Set your bot's user name. Must be used in conjunction with `as_user` set to false, otherwise ignored. See [authorship](https://slack.dev) below. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-as_user",
            display_name="As User",
            info="Pass true to update the message as the authed user. [Bot users](https://slack.dev) in this context are considered authed users. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. This field is required when not presenting `text`. If you don't include this field, the message's previous `attachments` will be retained. To remove previous `attachments`, include an empty array for this field. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-blocks",
            display_name="Blocks",
            info="A JSON-based array of [structured blocks](https://slack.dev), presented as a URL-encoded string. If you don't include this field, the message's previous `blocks` will be retained. To remove previous `blocks`, include an empty array for this field. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-channel",
            display_name="Channel",
            info="Channel containing the message to be updated.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames. Defaults to `none`. If you do not specify a value for this field, the original value set for the message will be overwritten with the default, `none`. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `client`, unlike `chat.postMessage`. Accepts either `none` or `full`. If you do not specify a value for this field, the original value set for the message will be overwritten with the default, `client`. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-text",
            display_name="Text",
            info="New text for the message, using the [default formatting rules](https://slack.dev). It's not required when presenting `blocks` or `attachments`. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-ts",
            display_name="Ts",
            info="Timestamp of the message to be updated.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_REMOVE_REACTION_FROM_ITEM-channel",
            display_name="Channel",
            info="Channel where the message to remove reaction from was posted.",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_REMOVE_REACTION_FROM_ITEM-file",
            display_name="File",
            info="File to remove reaction from.",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_REMOVE_REACTION_FROM_ITEM-file_comment",
            display_name="File Comment",
            info="File comment to remove reaction from.",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_REMOVE_REACTION_FROM_ITEM-name",
            display_name="Name",
            info="Reaction (emoji) name.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_REMOVE_REACTION_FROM_ITEM-timestamp",
            display_name="Timestamp",
            info="Timestamp of the message to remove reaction from.",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_FETCH_CONVERSATION_HISTORY-channel",
            display_name="Channel",
            info="Conversation ID to fetch history for.",
            show=False,
        ),
        IntInput(
            name="SLACK_FETCH_CONVERSATION_HISTORY-latest",
            display_name="Latest",
            info="End of time range of messages to include in results.",
            show=False,
        ),
        IntInput(
            name="SLACK_FETCH_CONVERSATION_HISTORY-oldest",
            display_name="Oldest",
            info="Start of time range of messages to include in results.",
            show=False,
        ),
        BoolInput(
            name="SLACK_FETCH_CONVERSATION_HISTORY-inclusive",
            display_name="Inclusive",
            info="Include messages with latest or oldest timestamp in results only when either timestamp is specified. ",
            show=False,
        ),
        IntInput(
            name="SLACK_FETCH_CONVERSATION_HISTORY-limit",
            display_name="Limit",
            info="The maximum number of items to return. Fewer than the requested number of items may be returned, even if the end of the users list hasn't been reached. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_FETCH_CONVERSATION_HISTORY-cursor",
            display_name="Cursor",
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first 'page' of the collection. See [pagination](https://slack.dev) for more detail. ",  # noqa: E501
            show=False,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-as_user",
            display_name="As User",
            info="Pass true to post the message as the authed user, instead of as a bot. Defaults to false. See [chat.postMessage](chat.postMessage#authorship). ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. ",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-blocks",
            display_name="Blocks",
            info="A JSON-based array of structured blocks, presented as a URL-encoded string. ",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-channel",
            display_name="Channel",
            info="Channel, private group, or DM channel to send message to. Can be an encoded ID, or a name. See [below](https://slack.dev) for more details. ",  # noqa: E501
            show=False,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames.",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `none`. See [chat.postMessage](chat.postMessage#formatting). ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-post_at",
            display_name="Post At",
            info="Unix EPOCH timestamp of time in future to send the message.",
            show=False,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-reply_broadcast",
            display_name="Reply Broadcast",
            info="Used in conjunction with `thread_ts` and indicates whether reply should be made visible to everyone in the channel or conversation. Defaults to `false`. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-text",
            display_name="Text",
            info="How this field works and whether it is required depends on other fields you use in your API call. [See below](https://slack.dev) for more detail. ",  # noqa: E501
            show=False,
        ),
        IntInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-thread_ts",
            display_name="Thread Ts",
            info="Provide another message's `ts` value to make this message a reply. Avoid using a reply's `ts` value; use its parent instead. ",  # noqa: E501
            show=False,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-unfurl_links",
            display_name="Unfurl Links",
            info="Pass true to enable unfurling of primarily text-based content.",
            show=False,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-unfurl_media",
            display_name="Unfurl Media",
            info="Pass false to disable unfurling of media content.",
            show=False,
        ),
        BoolInput(
            name="SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-exclude_archived",
            display_name="Exclude Archived",
            info="Set to `true` to exclude archived channels from the list",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-types",
            display_name="Types",
            info="Mix and match channel types by providing a comma-separated list of any combination of `public_channel`, `private_channel`, `mpim`, `im` ",  # noqa: E501
            show=False,
        ),
        IntInput(
            name="SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-limit",
            display_name="Limit",
            info="The maximum number of items to return. Fewer than the requested number of items may be returned, even if the end of the list hasn't been reached. Must be an integer no larger than 1000. ",  # noqa: E501
            show=False,
            value=1,
        ),
        MessageTextInput(
            name="SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-cursor",
            display_name="Cursor",
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first 'page' of the collection. See [pagination](https://slack.dev) for more detail. ",  # noqa: E501
            show=False,
        ),
        IntInput(
            name="SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-count",
            display_name="Count",
            info="Pass the number of results you want per 'page'. Maximum of `100`.",
            show=False,
            value=1,
        ),
        BoolInput(
            name="SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-highlight",
            display_name="Highlight",
            info="Pass a value of `true` to enable query highlight markers (see below).",
            show=False,
        ),
        IntInput(
            name="SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-page",
            display_name="Page",
            info="Page",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-query",
            display_name="Query",
            info="Search query.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-sort",
            display_name="Sort",
            info="Return matches sorted by either `score` or `timestamp`.",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY-sort_dir",
            display_name="Sort Dir",
            info="Change sort direction to ascending (`asc`) or descending (`desc`).",
            show=False,
        ),
        MessageTextInput(
            name="SLACK_ADD_REACTION_TO_AN_ITEM-channel",
            display_name="Channel",
            info="Channel where the message to add reaction to was posted.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_ADD_REACTION_TO_AN_ITEM-name",
            display_name="Name",
            info="Reaction (emoji) name.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_ADD_REACTION_TO_AN_ITEM-timestamp",
            display_name="Timestamp",
            info="Timestamp of the message to add reaction to.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_CREATE_A_REMINDER-text",
            display_name="Text",
            info="The content of the reminder",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_CREATE_A_REMINDER-time",
            display_name="Time",
            info="When this reminder should happen: the Unix timestamp (up to five years from now), the number of seconds until the reminder (if within 24 hours), or a natural language description (Ex. 'in 15 minutes,' or 'every Thursday') ",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_CREATE_A_REMINDER-user",
            display_name="User",
            info="The user who will receive the reminder. If no user is specified, the reminder will go to user who created it. ",  # noqa: E501
            show=False,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Response", method="execute_action"),
    ]

    def execute_action(self) -> Message:
        """Execute Slack action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            action_key = self._display_to_enum_map.get(self.action)

            enum_name = getattr(Action, action_key)  # type: ignore[arg-type]
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["parameters"]:
                    param_name = field.split("-", 1)[1] if "-" in field else field
                    value = getattr(self, field)

                    if value is None or value == "":
                        continue

                    if field in self._bool_variables:
                        value = bool(value)

                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            self.status = result
            return Message(text=str(result))
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action
            if self.action in self._actions_data:
                display_name = self._actions_data[self.action]["display_name"]
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def show_hide_fields(self, build_config: dict, field_value: Any):
        all_fields = set()
        for action_data in self._actions_data.values():
            all_fields.update(action_data["parameters"])

        for field in all_fields:
            build_config[field]["show"] = False

            if field in self._bool_variables:
                build_config[field]["value"] = None
            else:
                build_config[field]["value"] = ""

        action_key = self._display_to_enum_map.get(field_value)

        if action_key in self._actions_data:
            for field in self._actions_data[action_key]["parameters"]:
                build_config[field]["show"] = True

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        build_config["auth_status"]["show"] = True
        build_config["auth_status"]["advanced"] = False

        if field_name == "tool_mode":
            if field_value:
                build_config["action"]["show"] = False

                all_fields = set()
                for action_data in self._actions_data.values():
                    all_fields.update(action_data["parameters"])
                for field in all_fields:
                    build_config[field]["show"] = False

            else:
                build_config["action"]["show"] = True

        if field_name == "action":
            self.show_hide_fields(build_config, field_value)

        if hasattr(self, "api_key") and self.api_key != "":
            slack_display_names = list(self._display_to_enum_map.keys())
            build_config["action"]["options"] = slack_display_names

            try:
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)

                try:
                    entity.get_connection(app="slack")
                    build_config["auth_status"]["value"] = "✅"
                    build_config["auth_link"]["show"] = False

                except NoItemsFound:
                    auth_scheme = self._get_auth_scheme("slack")
                    if auth_scheme.auth_mode == "OAUTH2":
                        build_config["auth_link"]["show"] = True
                        build_config["auth_link"]["advanced"] = False
                        auth_url = self._initiate_default_connection(entity, "slack")
                        build_config["auth_link"]["value"] = auth_url
                        build_config["auth_status"]["value"] = "Click link to authenticate"

            except (ValueError, ConnectionError) as e:
                logger.error(f"Error checking auth status: {e}")
                build_config["auth_status"]["value"] = f"Error: {e!s}"

        return build_config

    def _get_auth_scheme(self, app_name: str) -> AppAuthScheme:
        """Get the primary auth scheme for an app.

        Args:
        app_name (str): The name of the app to get auth scheme for.

        Returns:
        AppAuthScheme: The auth scheme details.
        """
        toolset = self._build_wrapper()
        try:
            return toolset.get_auth_scheme_for_app(app=app_name.lower())
        except Exception:  # noqa: BLE001
            logger.exception(f"Error getting auth scheme for {app_name}")
            return None

    def _initiate_default_connection(self, entity: Any, app: str) -> str:
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

    def _build_wrapper(self) -> ComposioToolSet:
        """Build the Composio toolset wrapper.

        Returns:
        ComposioToolSet: The initialized toolset.

        Raises:
        ValueError: If the API key is not found or invalid.
        """
        try:
            if not self.api_key:
                msg = "Composio API Key is required"
                raise ValueError(msg)
            return ComposioToolSet(api_key=self.api_key)
        except ValueError as e:
            logger.error(f"Error building Composio wrapper: {e}")
            msg = "Please provide a valid Composio API Key in the component settings"
            raise ValueError(msg) from e

    async def _get_tools(self) -> list[Tool]:
        DISABLED_TOOLS = [ # Disabled temporarily
            "SLACK_ADD_REACTION_TO_AN_ITEM",
            "SLACK_FETCH_CONVERSATION_HISTORY",
            "SLACK_REMOVE_REACTION_FROM_ITEM"
        ]
        toolset = self._build_wrapper()
        tools = toolset.get_tools(actions=self._actions_data.keys())
        tools = [tool for tool in tools if tool.name not in DISABLED_TOOLS]
        for tool in tools:
            tool.tags = [tool.name]  # Assigning tags directly
        return tools

    @property
    def enabled_tools(self):
        return [
            "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL",
            "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY",
        ]
