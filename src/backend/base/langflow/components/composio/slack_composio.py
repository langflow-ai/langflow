from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    BoolInput,
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger


class ComposioSlackAPIComponent(ComposioBaseComponent):
    display_name: str = "Slack"
    description: str = "Slack API"
    name = "SlackAPI"
    icon = "Slack"
    documentation: str = "https://docs.composio.dev"
    app_name = "slack"

    _actions_data: dict = {
        "SLACK_ADD_REACTION_TO_AN_ITEM": {
            "display_name": "Add reaction to message",
            "action_fields": [
                "SLACK_ADD_REACTION_TO_AN_ITEM-channel",
                "SLACK_ADD_REACTION_TO_AN_ITEM-name",
                "SLACK_ADD_REACTION_TO_AN_ITEM-timestamp",
            ],
        },
        "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION": {
            "display_name": "List Users",
            "action_fields": [
                "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-limit",
                "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-cursor",
                "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION-include_locale",
            ],
        },
        "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS": {
            "display_name": "List Channels",
            "action_fields": [
                "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-exclude_archived",
                "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-types",
                "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-limit",
                "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS-cursor",
            ],
        },
        "SLACK_UPDATES_A_SLACK_MESSAGE": {
            "display_name": "Update Slack Chat Message",
            "action_fields": [
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
            "display_name": "Post Message To Channel",
            "action_fields": [
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
            "display_name": "Search Messages Endpoint",
            "action_fields": [
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
            "action_fields": [
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
            "action_fields": [
                "SLACK_REMOVE_REACTION_FROM_ITEM-channel",
                "SLACK_REMOVE_REACTION_FROM_ITEM-file",
                "SLACK_REMOVE_REACTION_FROM_ITEM-file_comment",
                "SLACK_REMOVE_REACTION_FROM_ITEM-name",
                "SLACK_REMOVE_REACTION_FROM_ITEM-timestamp",
            ],
        },
        "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME": {
            "display_name": "Schedule Message In Chat",
            "action_fields": [
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
            "display_name": "Add Reminder For User",
            "action_fields": [
                "SLACK_CREATE_A_REMINDER-text",
                "SLACK_CREATE_A_REMINDER-time",
                "SLACK_CREATE_A_REMINDER-user",
            ],
        },
    }

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}
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

    # Cache for action fields mapping
    _action_fields_cache: dict[str, set[str]] = {}
    _readonly_actions = frozenset(
        [  # "Add reaction to message": "SLACK_ADD_REACTION_TO_AN_ITEM", # Disabled temporarily
            "SLACK_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION",
            "SLACK_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS",
            "SLACK_UPDATES_A_SLACK_MESSAGE",
            "SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL",
            "SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY",
            # "Retrieve conversation history": "SLACK_FETCH_CONVERSATION_HISTORY", # Disabled temporarily
            # "Remove reactions from message": "SLACK_REMOVE_REACTION_FROM_ITEM", # Disabled temporarily
            "SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME",
            "SLACK_CREATE_A_REMINDER",
        ]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._all_fields = {
            field for action_data in self._actions_data.values() for field in action_data["action_fields"]
        }

        self._bool_variables = {
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

        self._default_tools = {
            self.sanitize_action_name("SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL").replace(" ", "-"),
            self.sanitize_action_name("SLACK_SEARCH_FOR_MESSAGES_WITH_QUERY").replace(" ", "-"),
        }
        # Build the action maps right away
        self._display_to_key_map = {data["display_name"]: key for key, data in self._actions_data.items()}
        self._key_to_display_map = {key: data["display_name"] for key, data in self._actions_data.items()}
        self._sanitized_names = {
            action: self._name_sanitizer.sub("-", self.sanitize_action_name(action)) for action in self._actions_data
        }

    inputs = [
        *ComposioBaseComponent._base_inputs,
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
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first `page` of the collection",  # noqa: E501
            show=False,
            advanced=True,
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
            info="Pass true to post the message as the authed user, instead of as a bot. Defaults to false",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. ",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-blocks",
            display_name="Blocks",
            info="A JSON-based array of structured blocks, presented as a URL-encoded string. ",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-channel",
            display_name="Channel",
            info="Channel, private group, or IM channel to send message to. Can be an encoded ID, or a name ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-icon_emoji",
            display_name="Icon Emoji",
            info="Emoji to use as the icon for this message. Overrides `icon_url`. Must be used in conjunction with `as_user` set to `false`, otherwise ignored",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-icon_url",
            display_name="Icon Url",
            info="URL to an image to use as the icon for this message. Must be used in conjunction with `as_user` set to false, otherwise ignored",  # noqa: E501
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-mrkdwn",
            display_name="Mrkdwn",
            info="Disable Slack markup parsing by setting to `false`. Enabled by default.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `none` ",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-reply_broadcast",
            display_name="Reply Broadcast",
            info="Used in conjunction with `thread_ts` and indicates whether reply should be made visible to everyone in the channel or conversation. Defaults to `false`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-text",
            display_name="Text",
            info="How this field works and whether it is required depends on other fields you use in your API call",
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
            advanced=True,
        ),
        BoolInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-unfurl_media",
            display_name="Unfurl Media",
            info="Pass false to disable unfurling of media content.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL-username",
            display_name="Username",
            info="Set your bot's user name. Must be used in conjunction with `as_user` set to false, otherwise ignored",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-as_user",
            display_name="As User",
            info="Pass true to update the message as the authed user",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. This field is required when not presenting `text`. If you don't include this field, the message's previous `attachments` will be retained. To remove previous `attachments`, include an empty array for this field. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-blocks",
            display_name="Blocks",
            info="A JSON-based array of structured blocks, presented as a URL-encoded string. If you don't include this field, the message's previous `blocks` will be retained. To remove previous `blocks`, include an empty array for this field. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-channel",
            display_name="Channel Id",
            info="Channel Id containing the message to be updated.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames. Defaults to `none`. If you do not specify a value for this field, the original value set for the message will be overwritten with the default, `none`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `client`, unlike `chat.postMessage`. Accepts either `none` or `full`. If you do not specify a value for this field, the original value set for the message will be overwritten with the default, `client`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_UPDATES_A_SLACK_MESSAGE-text",
            display_name="Text",
            info="New text for the message, using the default formatting rules. It's not required when presenting `blocks` or `attachments`. ",  # noqa: E501
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
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_REMOVE_REACTION_FROM_ITEM-file_comment",
            display_name="File Comment",
            info="File comment to remove reaction from.",
            show=False,
            advanced=True,
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
            advanced=True,
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
            info="Include messages with latest or oldest timestamp in results only when either timestamp is specified. ",  # noqa: E501
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
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first 'page' of the collection. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-as_user",
            display_name="As User",
            info="Pass true to post the message as the authed user, instead of as a bot. Defaults to false",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. ",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-blocks",
            display_name="Blocks",
            info="A JSON-based array of structured blocks, presented as a URL-encoded string. ",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-channel",
            display_name="Channel",
            info="Channel, private group, or DM channel to send message to. Can be an encoded ID, or a name",
            show=False,
            required=True,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `none`",
            show=False,
            advanced=True,
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
            advanced=True,
        ),
        MessageTextInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-text",
            display_name="Text",
            info="How this field works and whether it is required depends on other fields you use in your API call",
            show=False,
        ),
        IntInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-thread_ts",
            display_name="Thread Ts",
            info="Provide another message's `ts` value to make this message a reply. Avoid using a reply's `ts` value; use its parent instead. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-unfurl_links",
            display_name="Unfurl Links",
            info="Pass true to enable unfurling of primarily text-based content.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACK_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME-unfurl_media",
            display_name="Unfurl Media",
            info="Pass false to disable unfurling of media content.",
            show=False,
            advanced=True,
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
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first 'page' of the collection",  # noqa: E501
            show=False,
            advanced=True,
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
            info="Pass a value of `true` to enable query highlight markers",
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

    def execute_action(self):
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            # Get the display name from the action list
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
            # Use the display_to_key_map to get the action key
            action_key = self._display_to_key_map.get(display_name)
            if not action_key:
                msg = f"Invalid action: {display_name}"
                raise ValueError(msg)

            enum_name = getattr(Action, action_key)
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["action_fields"]:
                    value = getattr(self, field)

                    if value is None or value == "":
                        continue

                    if field in self._bool_variables:
                        value = bool(value)

                    param_name = field.split("-", 1)[1] if "-" in field else field
                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            if not result.get("successful"):
                return {"error": result.get("error", "No response")}

            result_data = result.get("data", [])
            if (
                len(result_data) != 1
                and not self._actions_data.get(action_key, {}).get("result_field")
                and self._actions_data.get(action_key, {}).get("get_result_field")
            ):
                msg = f"Expected a dict with a single key, got {len(result_data)} keys: {result_data.keys()}"
                raise ValueError(msg)
            if result_data:
                get_result_field = self._actions_data.get(action_key, {}).get("get_result_field", True)
                if get_result_field:
                    key = self._actions_data.get(action_key, {}).get("result_field", next(iter(result_data)))
                    return (
                        result_data.get(key)
                        if isinstance(result_data.get(key), dict)
                        else {"response": result_data.get(key)}
                    )  # noqa: E501
                return result_data if isinstance(result_data, dict) else {"response": result_data}
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)
