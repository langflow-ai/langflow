import json
from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger


class ComposioYoutubeAPIComponent(ComposioBaseComponent):
    display_name: str = "Youtube"
    description: str = "Youtube API"
    icon = "YouTube"
    documentation: str = "https://docs.composio.dev"
    app_name = "youtube"

    _actions_data: dict = {
        "YOUTUBE_GET_CHANNEL_ID_BY_HANDLE": {
            "display_name": "Get Channel ID by Handle",
            "action_fields": ["YOUTUBE_GET_CHANNEL_ID_BY_HANDLE_channel_handle"],
            "get_result_field": True,
            "result_field": "items",
        },
        "YOUTUBE_LIST_CAPTION_TRACK": {
            "display_name": "List Caption Track",
            "action_fields": ["YOUTUBE_LIST_CAPTION_TRACK_part", "YOUTUBE_LIST_CAPTION_TRACK_videoId"],
            "get_result_field": True,
            "result_field": "items",
        },
        "YOUTUBE_LIST_CHANNEL_VIDEOS": {
            "display_name": "List Channel Videos",
            "action_fields": [
                "YOUTUBE_LIST_CHANNEL_VIDEOS_channelId",
                "YOUTUBE_LIST_CHANNEL_VIDEOS_maxResults",
                "YOUTUBE_LIST_CHANNEL_VIDEOS_pageToken",
                "YOUTUBE_LIST_CHANNEL_VIDEOS_part",
            ],
            "get_result_field": True,
            "result_field": "items",
        },
        "YOUTUBE_LIST_USER_PLAYLISTS": {
            "display_name": "List User Playlists",
            "action_fields": [
                "YOUTUBE_LIST_USER_PLAYLISTS_maxResults",
                "YOUTUBE_LIST_USER_PLAYLISTS_pageToken",
                "YOUTUBE_LIST_USER_PLAYLISTS_part",
            ],
            "get_result_field": True,
            "result_field": "response_data",
        },
        "YOUTUBE_LIST_USER_SUBSCRIPTIONS": {
            "display_name": "List User Subscriptions",
            "action_fields": [
                "YOUTUBE_LIST_USER_SUBSCRIPTIONS_maxResults",
                "YOUTUBE_LIST_USER_SUBSCRIPTIONS_pageToken",
                "YOUTUBE_LIST_USER_SUBSCRIPTIONS_part",
            ],
            "get_result_field": True,
            "result_field": "items",
        },
        "YOUTUBE_LOAD_CAPTIONS": {
            "display_name": "Load Captions",
            "action_fields": ["YOUTUBE_LOAD_CAPTIONS_id", "YOUTUBE_LOAD_CAPTIONS_tfmt"],
            "get_result_field": True,
            "result_field": "data",
        },
        "YOUTUBE_SEARCH_YOU_TUBE": {
            "display_name": "Search YouTube",
            "action_fields": [
                "YOUTUBE_SEARCH_YOU_TUBE_maxResults",
                "YOUTUBE_SEARCH_YOU_TUBE_pageToken",
                "YOUTUBE_SEARCH_YOU_TUBE_part",
                "YOUTUBE_SEARCH_YOU_TUBE_q",
                "YOUTUBE_SEARCH_YOU_TUBE_type",
            ],
            "get_result_field": True,
            "result_field": "response_data",
        },
        "YOUTUBE_SUBSCRIBE_CHANNEL": {
            "display_name": "Subscribe Channel",
            "action_fields": ["YOUTUBE_SUBSCRIBE_CHANNEL_channelId"],
            "get_result_field": True,
            "result_field": "snippet",
        },
        "YOUTUBE_VIDEO_DETAILS": {
            "display_name": "Video Details",
            "action_fields": ["YOUTUBE_VIDEO_DETAILS_id", "YOUTUBE_VIDEO_DETAILS_part"],
            "get_result_field": True,
            "result_field": "items",
        },
    }

    _list_variables = {"YOUTUBE_UPDATE_VIDEO_tags"}

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}

    inputs = [
        *ComposioBaseComponent._base_inputs,
        MessageTextInput(
            name="YOUTUBE_GET_CHANNEL_ID_BY_HANDLE_channel_handle",
            display_name="Channel Handle",
            info="YouTube channel ID to subscribe to",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_CAPTION_TRACK_part",
            display_name="Part",
            info="Comma-separated list of one or more caption resource properties that the response will include",
            show=False,
            value="snippet",
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_CAPTION_TRACK_videoId",
            display_name="Video ID",
            info="YouTube video ID for which the API should return caption tracks",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_CHANNEL_VIDEOS_channelId",
            display_name="Channel ID",
            info="channel ID for which the API should return videos",
            show=False,
            required=True,
        ),
        IntInput(
            name="YOUTUBE_LIST_CHANNEL_VIDEOS_maxResults",
            display_name="Max Results",
            info="Maximum number of items that should be returned in the result set. Default is 5",
            show=False,
            value=5,
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_CHANNEL_VIDEOS_pageToken",
            display_name="Page Token",
            info="Token that identifies a page of results that has been returned by a previous API request",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_CHANNEL_VIDEOS_part",
            display_name="Part",
            info="Comma-separated list of one or more search resource properties that the API response will include",
            show=False,
            value="snippet",
        ),
        IntInput(
            name="YOUTUBE_LIST_USER_PLAYLISTS_maxResults",
            display_name="Max Results",
            info="Maximum number of items that should be returned in the result set. Default is 5",
            show=False,
            value=5,
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_USER_PLAYLISTS_pageToken",
            display_name="Page Token",
            info="Token that identifies a page of results that has been returned by a previous API request",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_USER_PLAYLISTS_part",
            display_name="Part",
            info="Comma-separated list of one or more playlist resource properties that the response will include",
            show=False,
            value="snippet",
        ),
        IntInput(
            name="YOUTUBE_LIST_USER_SUBSCRIPTIONS_maxResults",
            display_name="Max Results",
            info="Maximum number of items that should be returned in the result set. Default is 5",
            show=False,
            value=5,
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_USER_SUBSCRIPTIONS_pageToken",
            display_name="Page Token",
            info="Token that identifies a page of results that has been returned by a previous API request",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_LIST_USER_SUBSCRIPTIONS_part",
            display_name="Part",
            info="Comma-separated list of one or more subscription resource properties that the response will include",
            show=False,
            value="snippet,contentDetails",
        ),
        MessageTextInput(
            name="YOUTUBE_LOAD_CAPTIONS_id",
            display_name="ID",
            info="ID of the caption track to be downloaded. Note: You can only download captions for videos you own",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_LOAD_CAPTIONS_tfmt",
            display_name="Tfmt",
            info="API response should return the captions in SubRip subtitle format",
            show=False,
            value="srt",
        ),
        IntInput(
            name="YOUTUBE_SEARCH_YOU_TUBE_maxResults",
            display_name="Max Results",
            info="Maximum number of items that should be returned in the result set. Default is 5",
            show=False,
            value=5,
        ),
        MessageTextInput(
            name="YOUTUBE_SEARCH_YOU_TUBE_pageToken",
            display_name="Page Token",
            info="Token that identifies a page of results that has been returned by a previous API request",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_SEARCH_YOU_TUBE_part",
            display_name="Part",
            info="Comma-separated list of one or more search resource properties that the API response will include",
            show=False,
            value="snippet",
        ),
        MessageTextInput(
            name="YOUTUBE_SEARCH_YOU_TUBE_q",
            display_name="Search Query",
            info="Query term to search for",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_SEARCH_YOU_TUBE_type",
            display_name="Type",
            info="Restricts a search query to only retrieve a particular type of resource. The value can be one or more of: 'video', 'channel', 'playlist'",  # noqa: E501
            show=False,
            value="video",
        ),
        MessageTextInput(
            name="YOUTUBE_SUBSCRIBE_CHANNEL_channelId",
            display_name="Channel ID",
            info="YouTube channel ID to subscribe to",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_UPDATE_VIDEO_categoryId",
            display_name="Category ID",
            info="YouTube category ID of the video",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_UPDATE_VIDEO_description",
            display_name="Description",
            info="Description of the video",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_UPDATE_VIDEO_privacyStatus",
            display_name="Privacy Status",
            info="Privacy status of the video. Valid values are 'public', 'private', and 'unlisted'",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_UPDATE_VIDEO_tags",
            display_name="Tags",
            info="List of tags associated with the video",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_UPDATE_VIDEO_title",
            display_name="Title",
            info="The title of the video.",
            show=False,
        ),
        MessageTextInput(
            name="YOUTUBE_UPDATE_VIDEO_videoId",
            display_name="Video ID",
            info="YouTube video ID to be updated",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_VIDEO_DETAILS_id",
            display_name="ID",
            info="YouTube video ID for which the API should return details",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_VIDEO_DETAILS_part",
            display_name="Part",
            info="Comma-separated list of one or more video resource properties that the API response will include",
            show=False,
            value="snippet,contentDetails,statistics",
        ),
    ]

    def _find_key_recursively(self, data, key):
        """Recursively search for a key in nested dicts/lists and return its value if found."""
        if isinstance(data, dict):
            if key in data:
                return data[key]
            for v in data.values():
                found = self._find_key_recursively(v, key)
                if found is not None:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = self._find_key_recursively(item, key)
                if found is not None:
                    return found
        return None

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

                    if field in self._list_variables and value:
                        value = [item.strip() for item in value.split(",")]

                    param_name = field.replace(action_key + "_", "")

                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            if not result.get("successful"):
                message = result.get("data", {}).get("message", {})

                error_info = {"error": result.get("error", "No response")}
                if isinstance(message, str):
                    try:
                        parsed_message = json.loads(message)
                        if isinstance(parsed_message, dict) and "error" in parsed_message:
                            error_data = parsed_message["error"]
                            error_info = {
                                "error": {
                                    "code": error_data.get("code", "Unknown"),
                                    "message": error_data.get("message", "No error message"),
                                }
                            }
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Failed to parse error message as JSON: {e}")
                        error_info = {"error": str(message)}
                elif isinstance(message, dict) and "error" in message:
                    error_data = message["error"]
                    error_info = {
                        "error": {
                            "code": error_data.get("code", "Unknown"),
                            "message": error_data.get("message", "No error message"),
                        }
                    }

                return error_info

            result_data = result.get("data", [])
            action_data = self._actions_data.get(action_key, {})
            if action_data.get("get_result_field"):
                result_field = action_data.get("result_field")
                if result_field:
                    found = self._find_key_recursively(result_data, result_field)
                    if found is not None:
                        return found
                return result_data
            if result_data and isinstance(result_data, dict):
                return result_data[next(iter(result_data))]
            return result_data  # noqa: TRY300
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)

    def set_default_tools(self):
        self._default_tools = {
            self.sanitize_action_name("YOUTUBE_SEARCH_YOU_TUBE").replace(" ", "-"),
            self.sanitize_action_name("YOUTUBE_VIDEO_DETAILS").replace(" ", "-"),
        }
