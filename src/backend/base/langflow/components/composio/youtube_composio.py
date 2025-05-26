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
    icon = "Youtube"
    documentation: str = "https://docs.composio.dev"
    app_name = "youtube"

    _actions_data: dict = {
        "YOUTUBE_GET_CHANNEL_ID_BY_HANDLE": {
            "display_name": "Get Channel Id by Handle",
            "action_fields": ["YOUTUBE_GET_CHANNEL_ID_BY_HANDLE_channel_handle"],
        },
        "YOUTUBE_LIST_CAPTION_TRACK": {
            "display_name": "List caption track",
            "action_fields": ["YOUTUBE_LIST_CAPTION_TRACK_part", "YOUTUBE_LIST_CAPTION_TRACK_videoId"],
        },
        "YOUTUBE_LIST_CHANNEL_VIDEOS": {
            "display_name": "List channel videos",
            "action_fields": [
                "YOUTUBE_LIST_CHANNEL_VIDEOS_channelId",
                "YOUTUBE_LIST_CHANNEL_VIDEOS_maxResults",
                "YOUTUBE_LIST_CHANNEL_VIDEOS_pageToken",
                "YOUTUBE_LIST_CHANNEL_VIDEOS_part",
            ],
        },
        "YOUTUBE_LIST_USER_PLAYLISTS": {
            "display_name": "List user playlists",
            "action_fields": [
                "YOUTUBE_LIST_USER_PLAYLISTS_maxResults",
                "YOUTUBE_LIST_USER_PLAYLISTS_pageToken",
                "YOUTUBE_LIST_USER_PLAYLISTS_part",
            ],
        },
        "YOUTUBE_LIST_USER_SUBSCRIPTIONS": {
            "display_name": "List user subscriptions",
            "action_fields": [
                "YOUTUBE_LIST_USER_SUBSCRIPTIONS_maxResults",
                "YOUTUBE_LIST_USER_SUBSCRIPTIONS_pageToken",
                "YOUTUBE_LIST_USER_SUBSCRIPTIONS_part",
            ],
        },
        "YOUTUBE_LOAD_CAPTIONS": {
            "display_name": "Load captions",
            "action_fields": ["YOUTUBE_LOAD_CAPTIONS_id", "YOUTUBE_LOAD_CAPTIONS_tfmt"],
        },
        "YOUTUBE_SEARCH_YOU_TUBE": {
            "display_name": "Search you tube",
            "action_fields": [
                "YOUTUBE_SEARCH_YOU_TUBE_maxResults",
                "YOUTUBE_SEARCH_YOU_TUBE_pageToken",
                "YOUTUBE_SEARCH_YOU_TUBE_part",
                "YOUTUBE_SEARCH_YOU_TUBE_q",
                "YOUTUBE_SEARCH_YOU_TUBE_type",
            ],
        },
        "YOUTUBE_SUBSCRIBE_CHANNEL": {
            "display_name": "Subscribe channel",
            "action_fields": ["YOUTUBE_SUBSCRIBE_CHANNEL_channelId"],
        },
        "YOUTUBE_UPDATE_THUMBNAIL": {
            "display_name": "Update thumbnail",
            "action_fields": ["YOUTUBE_UPDATE_THUMBNAIL_thumbnailUrl", "YOUTUBE_UPDATE_THUMBNAIL_videoId"],
        },
        "YOUTUBE_UPDATE_VIDEO": {
            "display_name": "Update video",
            "action_fields": [
                "YOUTUBE_UPDATE_VIDEO_categoryId",
                "YOUTUBE_UPDATE_VIDEO_description",
                "YOUTUBE_UPDATE_VIDEO_privacyStatus",
                "YOUTUBE_UPDATE_VIDEO_tags",
                "YOUTUBE_UPDATE_VIDEO_title",
                "YOUTUBE_UPDATE_VIDEO_videoId",
            ],
        },
        "YOUTUBE_UPLOAD_VIDEO": {
            "display_name": "Upload video",
            "action_fields": [
                "YOUTUBE_UPLOAD_VIDEO_categoryId",
                "YOUTUBE_UPLOAD_VIDEO_description",
                "YOUTUBE_UPLOAD_VIDEO_privacyStatus",
                "YOUTUBE_UPLOAD_VIDEO_tags",
                "YOUTUBE_UPLOAD_VIDEO_title",
                "YOUTUBE_UPLOAD_VIDEO_videoFilePath",
            ],
        },
        "YOUTUBE_VIDEO_DETAILS": {
            "display_name": "Video details",
            "action_fields": ["YOUTUBE_VIDEO_DETAILS_id", "YOUTUBE_VIDEO_DETAILS_part"],
        },
    }

    _list_variables = {"YOUTUBE_UPDATE_VIDEO_tags", "YOUTUBE_UPLOAD_VIDEO_tags"}

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}

    _bool_variables = {}

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
            name="YOUTUBE_UPDATE_THUMBNAIL_thumbnailUrl",
            display_name="Thumbnail URL",
            info="URL of the new thumbnail image",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_UPDATE_THUMBNAIL_videoId",
            display_name="Video ID",
            info="YouTube video ID for which the thumbnail should be updated",
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
            name="YOUTUBE_UPLOAD_VIDEO_categoryId",
            display_name="Category ID",
            info="YouTube category ID of the video",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_UPLOAD_VIDEO_description",
            display_name="Description",
            info="The description of the video",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_UPLOAD_VIDEO_privacyStatus",
            display_name="Privacy Status",
            info="The privacy status of the video. Valid values are 'public', 'private', and 'unlisted'",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_UPLOAD_VIDEO_tags",
            display_name="Tags",
            info="List of tags associated with the video",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_UPLOAD_VIDEO_title",
            display_name="Title",
            info="The title of the video",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="YOUTUBE_UPLOAD_VIDEO_videoFilePath",
            display_name="Video File Path",
            info="File path of the video to be uploaded",
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

            return result.get("data", []).get("response_data", [])
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
