from typing import Any
from urllib.error import HTTPError

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, MessageTextInput, SecretStrInput
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output


class YouTubeChannelComponent(Component):
    """A component that retrieves detailed information about YouTube channels."""

    display_name: str = "YouTube Channel"
    description: str = "Retrieves detailed information and statistics about YouTube channels as a DataFrame."
    icon: str = "YouTube"

    # Constants
    CHANNEL_ID_LENGTH = 24
    QUOTA_EXCEEDED_STATUS = 403
    NOT_FOUND_STATUS = 404
    MAX_PLAYLIST_RESULTS = 10

    inputs = [
        MessageTextInput(
            name="channel_url",
            display_name="Channel URL or ID",
            info="The URL or ID of the YouTube channel.",
            tool_mode=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="YouTube API Key",
            info="Your YouTube Data API key.",
            required=True,
        ),
        BoolInput(
            name="include_statistics",
            display_name="Include Statistics",
            value=True,
            info="Include channel statistics (views, subscribers, videos).",
        ),
        BoolInput(
            name="include_branding",
            display_name="Include Branding",
            value=True,
            info="Include channel branding settings (banner, thumbnails).",
            advanced=True,
        ),
        BoolInput(
            name="include_playlists",
            display_name="Include Playlists",
            value=False,
            info="Include channel's public playlists.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="channel_df", display_name="Channel Info", method="get_channel_info"),
    ]

    def _extract_channel_id(self, channel_url: str) -> str:
        """Extracts the channel ID from various YouTube channel URL formats."""
        import re

        if channel_url.startswith("UC") and len(channel_url) == self.CHANNEL_ID_LENGTH:
            return channel_url

        patterns = {
            "custom_url": r"youtube\.com\/c\/([^\/\n?]+)",
            "channel_id": r"youtube\.com\/channel\/([^\/\n?]+)",
            "user": r"youtube\.com\/user\/([^\/\n?]+)",
            "handle": r"youtube\.com\/@([^\/\n?]+)",
        }

        for pattern_type, pattern in patterns.items():
            match = re.search(pattern, channel_url)
            if match:
                if pattern_type == "channel_id":
                    return match.group(1)
                return self._get_channel_id_by_name(match.group(1), pattern_type)

        return channel_url

    def _get_channel_id_by_name(self, channel_name: str, identifier_type: str) -> str:
        """Gets the channel ID using the channel name or custom URL."""
        youtube = None
        try:
            youtube = build("youtube", "v3", developerKey=self.api_key)

            if identifier_type == "handle":
                channel_name = channel_name.lstrip("@")

            request = youtube.search().list(part="id", q=channel_name, type="channel", maxResults=1)
            response = request.execute()

            if response["items"]:
                return response["items"][0]["id"]["channelId"]

            error_msg = f"Could not find channel ID for: {channel_name}"
            raise ValueError(error_msg)

        except (HttpError, HTTPError) as e:
            error_msg = f"YouTube API error while getting channel ID: {e!s}"
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error while getting channel ID: {e!s}"
            raise ValueError(error_msg) from e
        finally:
            if youtube:
                youtube.close()

    def _get_channel_playlists(self, youtube: Any, channel_id: str) -> list[dict[str, Any]]:
        """Gets the public playlists for a channel."""
        try:
            playlists_request = youtube.playlists().list(
                part="snippet,contentDetails",
                channelId=channel_id,
                maxResults=self.MAX_PLAYLIST_RESULTS,
            )
            playlists_response = playlists_request.execute()
            playlists = []

            for item in playlists_response.get("items", []):
                playlist_data = {
                    "playlist_title": item["snippet"]["title"],
                    "playlist_description": item["snippet"]["description"],
                    "playlist_id": item["id"],
                    "playlist_video_count": item["contentDetails"]["itemCount"],
                    "playlist_published_at": item["snippet"]["publishedAt"],
                    "playlist_thumbnail_url": item["snippet"]["thumbnails"]["default"]["url"],
                }
                playlists.append(playlist_data)

            return playlists
        except (HttpError, HTTPError) as e:
            return [{"error": str(e)}]
        else:
            return playlists

    def get_channel_info(self) -> DataFrame:
        """Retrieves channel information and returns it as a DataFrame."""
        youtube = None
        try:
            # Get channel ID and initialize YouTube API client
            channel_id = self._extract_channel_id(self.channel_url)
            youtube = build("youtube", "v3", developerKey=self.api_key)

            # Prepare parts for the API request
            parts = ["snippet", "contentDetails"]
            if self.include_statistics:
                parts.append("statistics")
            if self.include_branding:
                parts.append("brandingSettings")

            # Get channel information
            channel_response = youtube.channels().list(part=",".join(parts), id=channel_id).execute()

            if not channel_response["items"]:
                return DataFrame(pd.DataFrame({"error": ["Channel not found"]}))

            channel_info = channel_response["items"][0]

            # Build basic channel data
            channel_data = {
                "title": [channel_info["snippet"]["title"]],
                "description": [channel_info["snippet"]["description"]],
                "custom_url": [channel_info["snippet"].get("customUrl", "")],
                "published_at": [channel_info["snippet"]["publishedAt"]],
                "country": [channel_info["snippet"].get("country", "Not specified")],
                "channel_id": [channel_id],
            }

            # Add thumbnails
            for size, thumb in channel_info["snippet"]["thumbnails"].items():
                channel_data[f"thumbnail_{size}"] = [thumb["url"]]

            # Add statistics if requested
            if self.include_statistics:
                stats = channel_info["statistics"]
                channel_data.update(
                    {
                        "view_count": [int(stats.get("viewCount", 0))],
                        "subscriber_count": [int(stats.get("subscriberCount", 0))],
                        "hidden_subscriber_count": [stats.get("hiddenSubscriberCount", False)],
                        "video_count": [int(stats.get("videoCount", 0))],
                    }
                )

            # Add branding if requested
            if self.include_branding:
                branding = channel_info.get("brandingSettings", {})
                channel_data.update(
                    {
                        "brand_title": [branding.get("channel", {}).get("title", "")],
                        "brand_description": [branding.get("channel", {}).get("description", "")],
                        "brand_keywords": [branding.get("channel", {}).get("keywords", "")],
                        "brand_banner_url": [branding.get("image", {}).get("bannerExternalUrl", "")],
                    }
                )

            # Create the initial DataFrame
            channel_df = pd.DataFrame(channel_data)

            # Add playlists if requested
            if self.include_playlists:
                playlists = self._get_channel_playlists(youtube, channel_id)
                if playlists and "error" not in playlists[0]:
                    # Create a DataFrame for playlists
                    playlists_df = pd.DataFrame(playlists)
                    # Join with main DataFrame
                    channel_df = pd.concat([channel_df] * len(playlists_df), ignore_index=True)
                    for column in playlists_df.columns:
                        channel_df[column] = playlists_df[column].to_numpy()

            return DataFrame(channel_df)

        except (HttpError, HTTPError, Exception) as e:
            return DataFrame(pd.DataFrame({"error": [str(e)]}))
        finally:
            if youtube:
                youtube.close()
