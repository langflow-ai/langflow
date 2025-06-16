from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    BoolInput,
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger


class ComposioSLACKBOTAPIComponent(ComposioBaseComponent):
    display_name: str = "Slackbot"
    description: str = "Slackbot API"
    icon = "Slackbot"
    documentation: str = "https://docs.composio.dev"
    app_name = "slackbot"
    
    _actions_data: dict = {
                "SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION": {
            "display_name": "List Users",
            "action_fields": [
                "SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_limit",
                "SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_cursor",
                "SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_include_locale",
            ],
            "get_result_field": True,
            "result_field": "members",
        },
        "SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS": {
            "display_name": "List Channels",
            "action_fields": [
                "SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_exclude_archived",
                "SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_types",
                "SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_limit",
                "SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_cursor",
            ],
            "get_result_field": True,
            "result_field": "channels",
        },
        "SLACKBOT_UPDATES_A_SLACK_MESSAGE": {
            "display_name": "Update Slack Chat Message",
            "action_fields": [
                "SLACKBOT_UPDATES_A_SLACK_MESSAGE_as_user",
                "SLACKBOT_UPDATES_A_SLACK_MESSAGE_attachments",
                "SLACKBOT_UPDATES_A_SLACK_MESSAGE_blocks",
                "SLACKBOT_UPDATES_A_SLACK_MESSAGE_channel",
                "SLACKBOT_UPDATES_A_SLACK_MESSAGE_link_names",
                "SLACKBOT_UPDATES_A_SLACK_MESSAGE_parse",
                "SLACKBOT_UPDATES_A_SLACK_MESSAGE_text",
                "SLACKBOT_UPDATES_A_SLACK_MESSAGE_ts",
            ],
        },
        "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL": {
            "display_name": "Post Message To Channel",
            "action_fields": [
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_as_user",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_attachments",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_blocks",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_channel",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_icon_emoji",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_icon_url",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_link_names",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_mrkdwn",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_parse",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_reply_broadcast",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_text",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_thread_ts",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_unfurl_links",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_unfurl_media",
                "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_username",
            ],
        },
        "SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY": {
            "display_name": "Search Messages Endpoint",
            "action_fields": [
                "SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_count",
                "SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_highlight",
                "SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_page",
                "SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_query",
                "SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_sort",
                "SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_sort_dir",
            ],
        },
        "SLACKBOT_FETCH_CONVERSATION_HISTORY": {
            "display_name": "Retrieve conversation history",
            "action_fields": [
                "SLACKBOT_FETCH_CONVERSATION_HISTORY_channel",
                "SLACKBOT_FETCH_CONVERSATION_HISTORY_latest",
                "SLACKBOT_FETCH_CONVERSATION_HISTORY_oldest",
                "SLACKBOT_FETCH_CONVERSATION_HISTORY_inclusive",
                "SLACKBOT_FETCH_CONVERSATION_HISTORY_limit",
                "SLACKBOT_FETCH_CONVERSATION_HISTORY_cursor",
            ],
        },
        "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME": {
            "display_name": "Schedule Message In Chat",
            "action_fields": [
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_as_user",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_attachments",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_blocks",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_channel",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_link_names",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_parse",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_post_at",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_reply_broadcast",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_text",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_thread_ts",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_unfurl_links",
                "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_unfurl_media",
            ],
        },
        "SLACKBOT_CREATE_A_REMINDER": {
            "display_name": "Add Reminder For User",
            "action_fields": [
                "SLACKBOT_CREATE_A_REMINDER_text",
                "SLACKBOT_CREATE_A_REMINDER_time",
                "SLACKBOT_CREATE_A_REMINDER_user",
            ],
        },
    }
    
    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}
    
    _bool_variables = {
        "SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_include_locale",
        "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_as_user",
        "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_link_names",
        "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_mrkdwn",
        "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_reply_broadcast",
        "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_unfurl_links",
        "SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_unfurl_media",
        "SLACKBOT_FETCH_CONVERSATION_HISTORY_inclusive",
        "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_as_user",
        "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_link_names",
        "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_reply_broadcast",
        "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_unfurl_links",
        "SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_unfurl_media",
        "SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_exclude_archived",
        "SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_highlight",
    }
    
    inputs = [
        *ComposioBaseComponent._base_inputs,
        IntInput(
            name="SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_limit",
            display_name="Limit",
            info="The maximum number of items to return. Fewer than the requested number of items may be returned, even if the end of the users list hasn't been reached. Providing no `limit` value will result in Slack attempting to deliver you the entire result set. If the collection is too large you may experience `limit_required` or HTTP 500 errors. ",  # noqa: E501
            show=False,
            value=1,
        ),
        MessageTextInput(
            name="SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_cursor",
            display_name="Cursor",
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first `page` of the collection",  # noqa: E501
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION_include_locale",
            display_name="Include Locale",
            info="Set this to `true` to receive the locale for users. Defaults to `false`",
            show=False,
        ),
        BoolInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_as_user",
            display_name="As User",
            info="Pass true to post the message as the authed user, instead of as a bot. Defaults to false",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. ",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_blocks",
            display_name="Blocks",
            info="A JSON-based array of structured blocks, presented as a URL-encoded string. ",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_channel",
            display_name="Channel",
            info="Channel, private group, or IM channel to send message to. Can be an encoded ID, or a name ",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_icon_emoji",
            display_name="Icon Emoji",
            info="Emoji to use as the icon for this message. Overrides `icon_url`. Must be used in conjunction with `as_user` set to `false`, otherwise ignored",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_icon_url",
            display_name="Icon Url",
            info="URL to an image to use as the icon for this message. Must be used in conjunction with `as_user` set to false, otherwise ignored",  # noqa: E501
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_mrkdwn",
            display_name="Mrkdwn",
            info="Disable Slack markup parsing by setting to `false`. Enabled by default.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `none` ",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_reply_broadcast",
            display_name="Reply Broadcast",
            info="Used in conjunction with `thread_ts` and indicates whether reply should be made visible to everyone in the channel or conversation. Defaults to `false`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_text",
            display_name="Text",
            info="How this field works and whether it is required depends on other fields you use in your API call",
            show=False,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_thread_ts",
            display_name="Thread Ts",
            info="Provide another message's `ts` value to make this message a reply. Avoid using a reply's `ts` value; use its parent instead. ",  # noqa: E501
            show=False,
        ),
        BoolInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_unfurl_links",
            display_name="Unfurl Links",
            info="Pass true to enable unfurling of primarily text-based content.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_unfurl_media",
            display_name="Unfurl Media",
            info="Pass false to disable unfurling of media content.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL_username",
            display_name="Username",
            info="Set your bot's user name. Must be used in conjunction with `as_user` set to false, otherwise ignored",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_UPDATES_A_SLACK_MESSAGE_as_user",
            display_name="As User",
            info="Pass true to update the message as the authed user",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_UPDATES_A_SLACK_MESSAGE_attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. This field is required when not presenting `text`. If you don't include this field, the message's previous `attachments` will be retained. To remove previous `attachments`, include an empty array for this field. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_UPDATES_A_SLACK_MESSAGE_blocks",
            display_name="Blocks",
            info="A JSON-based array of structured blocks, presented as a URL-encoded string. If you don't include this field, the message's previous `blocks` will be retained. To remove previous `blocks`, include an empty array for this field. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_UPDATES_A_SLACK_MESSAGE_channel",
            display_name="Channel ID",
            info="Channel ID containing the message to be updated.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACKBOT_UPDATES_A_SLACK_MESSAGE_link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames. Defaults to `none`. If you do not specify a value for this field, the original value set for the message will be overwritten with the default, `none`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_UPDATES_A_SLACK_MESSAGE_parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `client`, unlike `chat.postMessage`. Accepts either `none` or `full`. If you do not specify a value for this field, the original value set for the message will be overwritten with the default, `client`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_UPDATES_A_SLACK_MESSAGE_text",
            display_name="Text",
            info="New text for the message, using the default formatting rules. It's not required when presenting `blocks` or `attachments`. ",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="SLACKBOT_UPDATES_A_SLACK_MESSAGE_ts",
            display_name="Ts",
            info="Timestamp of the message to be updated.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACKBOT_FETCH_CONVERSATION_HISTORY_channel",
            display_name="Channel ID",
            info="Channel ID to fetch history for.",
            show=False,
        ),
        IntInput(
            name="SLACKBOT_FETCH_CONVERSATION_HISTORY_latest",
            display_name="Latest",
            info="End of time range of messages to include in results.",
            show=False,
            advanced=True,
        ),
        IntInput(
            name="SLACKBOT_FETCH_CONVERSATION_HISTORY_oldest",
            display_name="Oldest",
            info="Start of time range of messages to include in results.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_FETCH_CONVERSATION_HISTORY_inclusive",
            display_name="Inclusive",
            info="Include messages with latest or oldest timestamp in results only when either timestamp is specified. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="SLACKBOT_FETCH_CONVERSATION_HISTORY_limit",
            display_name="Limit",
            info="The maximum number of items to return. Fewer than the requested number of items may be returned, even if the end of the users list hasn't been reached. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_FETCH_CONVERSATION_HISTORY_cursor",
            display_name="Cursor",
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first 'page' of the collection. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_as_user",
            display_name="As User",
            info="Pass true to post the message as the authed user, instead of as a bot. Defaults to false",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_attachments",
            display_name="Attachments",
            info="A JSON-based array of structured attachments, presented as a URL-encoded string. ",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_blocks",
            display_name="Blocks",
            info="A JSON-based array of structured blocks, presented as a URL-encoded string. ",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_channel",
            display_name="Channel",
            info="Channel, private group, or DM channel to send message to. Can be an encoded ID, or a name",
            show=False,
            required=True,
        ),
        BoolInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_link_names",
            display_name="Link Names",
            info="Find and link channel names and usernames.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_parse",
            display_name="Parse",
            info="Change how messages are treated. Defaults to `none`",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_post_at",
            display_name="Post At",
            info="Unix EPOCH timestamp of time in future to send the message.",
            show=False,
        ),
        BoolInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_reply_broadcast",
            display_name="Reply Broadcast",
            info="Used in conjunction with `thread_ts` and indicates whether reply should be made visible to everyone in the channel or conversation. Defaults to `false`. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_text",
            display_name="Text",
            info="How this field works and whether it is required depends on other fields you use in your API call",
            show=False,
        ),
        IntInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_thread_ts",
            display_name="Thread Ts",
            info="Provide another message's `ts` value to make this message a reply. Avoid using a reply's `ts` value; use its parent instead. ",  # noqa: E501
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_unfurl_links",
            display_name="Unfurl Links",
            info="Pass true to enable unfurling of primarily text-based content.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_SCHEDULES_A_MESSAGE_TO_A_CHANNEL_AT_A_SPECIFIED_TIME_unfurl_media",
            display_name="Unfurl Media",
            info="Pass false to disable unfurling of media content.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_exclude_archived",
            display_name="Exclude Archived",
            info="Set to `true` to exclude archived channels from the list",
            show=False,
        ),
        MessageTextInput(
            name="SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_types",
            display_name="Types",
            info="Mix and match channel types by providing a comma-separated list of any combination of `public_channel`, `private_channel`, `mpim`, `im` ",  # noqa: E501
            show=False,
        ),
        IntInput(
            name="SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_limit",
            display_name="Limit",
            info="The maximum number of items to return. Fewer than the requested number of items may be returned, even if the end of the list hasn't been reached. Must be an integer no larger than 1000. ",  # noqa: E501
            show=False,
            value=1,
        ),
        MessageTextInput(
            name="SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS_cursor",
            display_name="Cursor",
            info="Paginate through collections of data by setting the `cursor` parameter to a `next_cursor` attribute returned by a previous request's `response_metadata`. Default value fetches the first 'page' of the collection",  # noqa: E501
            show=False,
            advanced=True,
        ),
        IntInput(
            name="SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_count",
            display_name="Count",
            info="Pass the number of results you want per 'page'. Maximum of `100`.",
            show=False,
            value=1,
            advanced=True,
        ),
        BoolInput(
            name="SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_highlight",
            display_name="Highlight",
            info="Pass a value of `true` to enable query highlight markers",
            show=False,
            advanced=True,
        ),
        IntInput(
            name="SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_page",
            display_name="Page",
            info="Page",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_query",
            display_name="Query",
            info="Search query.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_sort",
            display_name="Sort",
            info="Return matches sorted by either `score` or `timestamp`.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY_sort_dir",
            display_name="Sort Dir",
            info="Change sort direction to ascending (`asc`) or descending (`desc`).",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="SLACKBOT_CREATE_A_REMINDER_text",
            display_name="Text",
            info="The content of the reminder",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACKBOT_CREATE_A_REMINDER_time",
            display_name="Time",
            info="When this reminder should happen: the Unix timestamp (up to five years from now), the number of seconds until the reminder (if within 24 hours), or a natural language description (Ex. 'in 15 minutes,' or 'every Thursday') ",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="SLACKBOT_CREATE_A_REMINDER_user",
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
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
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

                    param_name = field.replace(action_key + "_", "")

                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            if not result.get("successful"):
                return {"error": result.get("error", "No response")}

            result_data = result.get("data", {})
            actions_data = self._actions_data.get(action_key, {})
            
            # If 'get_result_field' is True and 'result_field' is specified, extract the data
            # using 'result_field'. Otherwise, fall back to the entire 'data' field in the response.
            if actions_data.get("get_result_field") and actions_data.get("result_field"):
                result_data = result_data.get(actions_data.get("result_field"), result.get("data", []))
            elif actions_data.get("get_result_field") and not actions_data.get("result_field"):
                # If get_result_field is True but no specific result_field is defined,
                # validate that we have a dict with a single key
                if isinstance(result_data, dict) and len(result_data) != 1:
                    msg = f"Expected a dict with a single key, got {len(result_data)} keys: {result_data.keys()}"
                    raise ValueError(msg)
            
            # Transform list actions to numbered dictionary
            if (action_key in ["SLACKBOT_LIST_ALL_SLACK_TEAM_CHANNELS_WITH_VARIOUS_FILTERS", 
                             "SLACKBOT_LIST_ALL_SLACK_TEAM_USERS_WITH_PAGINATION"] 
                and isinstance(result_data, list)):
                # Convert array to numbered dictionary
                numbered_dict = {}
                for index, item in enumerate(result_data):
                    numbered_dict[str(index + 1)] = item
                result_data = numbered_dict
            
            return result_data
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)

    def set_default_tools(self):
        self._default_tools = {
            self.sanitize_action_name("SLACKBOT_SENDS_A_MESSAGE_TO_A_SLACK_CHANNEL").replace(" ", "-"),
            self.sanitize_action_name("SLACKBOT_SEARCH_FOR_MESSAGES_WITH_QUERY").replace(" ", "-"),
        }