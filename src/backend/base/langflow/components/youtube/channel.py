from typing import Any
from urllib.error import HTTPError

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from langflow.custom import Component
from langflow.inputs import BoolInput, MessageTextInput, SecretStrInput
from langflow.schema import Data
from langflow.template import Output


class YouTubeError(Exception):
    """Base exception class for YouTube-related errors."""


class YouTubeAPIError(YouTubeError):
    """Exception raised for YouTube API-related errors."""


class YouTubeChannelComponent(Component):
    """A component that retrieves detailed information about YouTube channels."""

    display_name: str = "YouTube Channel"
    description: str = "Retrieves detailed information and statistics about YouTube channels."
    icon: str = "YouTube"
    name = "YouTubeChannel"

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
        Output(name="channel_data", display_name="Channel Data", method="get_channel_info"),
    ]

    def _extract_channel_id(self, channel_url: str) -> str:
        """Extracts the channel ID from various YouTube channel URL formats.

        Args:
            channel_url (str): The URL or ID of the YouTube channel

        Returns:
            str: The channel ID
        """
        import re

        # If it's already a channel ID (starts with UC)
        if channel_url.startswith("UC") and len(channel_url) == self.CHANNEL_ID_LENGTH:
            return channel_url

        # Different URL patterns
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
                # Need to make an API call to get the channel ID
                return self._get_channel_id_by_name(match.group(1), pattern_type)

        # If no patterns match, return the input as is
        return channel_url

    def _get_channel_id_by_name(self, channel_name: str, identifier_type: str) -> str:
        """Gets the channel ID using the channel name or custom URL.

        Args:
            channel_name (str): The channel name or custom URL
            identifier_type (str): The type of identifier ('custom_url', 'user', or 'handle')

        Returns:
            str: The channel ID

        Raises:
            YouTubeError: If channel ID cannot be found or API error occurs
        """
        try:
            youtube = build("youtube", "v3", developerKey=self.api_key)

            if identifier_type == "handle":
                # Remove @ from handle
                channel_name = channel_name.lstrip("@")

            # Search for the channel
            request = youtube.search().list(part="id", q=channel_name, type="channel", maxResults=1)
            response = request.execute()

            if response["items"]:
                return response["items"][0]["id"]["channelId"]

            error_msg = f"Could not find channel ID for: {channel_name}"
            raise YouTubeError(error_msg)

        except (HttpError, HTTPError) as e:
            error_msg = f"YouTube API error while getting channel ID: {e!s}"
            raise YouTubeAPIError(error_msg) from e

        except YouTubeError:
            raise

        except Exception as e:
            error_msg = f"Unexpected error while getting channel ID: {e!s}"
            raise YouTubeError(error_msg) from e

    def _get_channel_playlists(self, youtube: Any, channel_id: str) -> list[dict[str, Any]]:
        """Gets the public playlists for a channel.

        Args:
            youtube: YouTube API client
            channel_id (str): The channel ID

        Returns:
            List[Dict[str, Any]]: List of playlist information
        """
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
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "playlist_id": item["id"],
                    "video_count": item["contentDetails"]["itemCount"],
                    "published_at": item["snippet"]["publishedAt"],
                    "thumbnail_url": item["snippet"]["thumbnails"]["default"]["url"],
                }
                playlists.append(playlist_data)

        except (HttpError, HTTPError) as e:
            error_msg = f"YouTube API error while fetching playlists: {e!s}"
            return [{"error": error_msg}]

        except (ValueError, KeyError, AttributeError) as e:
            error_msg = f"Error processing playlist data: {e!s}"
            return [{"error": error_msg}]

        except (ConnectionError, TimeoutError) as e:
            error_msg = f"Network error while fetching playlists: {e!s}"
            return [{"error": error_msg}]

        return playlists

    def get_channel_info(self) -> Data:
        """Retrieves detailed information about a YouTube channel.

        Returns:
            Data: A Data object containing channel information
        """
        try:
            # Extract channel ID from URL
            channel_id = self._extract_channel_id(self.channel_url)

            # Initialize YouTube API client
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
                error_data = {"error": "Channel not found"}
                self.status = error_data
                return Data(data=error_data)

            channel_info = channel_response["items"][0]
            channel_data = self._build_channel_data(channel_info, channel_id)

            self.status = channel_data
            return Data(data=channel_data)

        except HttpError as e:
            if e.resp.status == self.QUOTA_EXCEEDED_STATUS:
                error_message = "API quota exceeded or access forbidden."
            elif e.resp.status == self.NOT_FOUND_STATUS:
                error_message = "Channel not found."
            else:
                error_message = f"YouTube API error: {e!s}"

            error_data = {"error": error_message}
            self.status = error_data
            return Data(data=error_data)

        except YouTubeError as e:
            error_data = {"error": str(e)}
            self.status = error_data
            return Data(data=error_data)

        except (ValueError, KeyError, AttributeError) as e:
            error_msg = f"Error processing channel data: {e!s}"
            error_data = {"error": error_msg}
            self.status = error_data
            return Data(data=error_data)

        except (ConnectionError, TimeoutError) as e:
            error_msg = f"Network error: {e!s}"
            error_data = {"error": error_msg}
            self.status = error_data
            return Data(data=error_data)

    def _build_channel_data(self, channel_info: dict[str, Any], channel_id: str) -> dict[str, Any]:
        """Builds the channel data dictionary from the API response.

        Args:
            channel_info: Raw channel information from YouTube API
            channel_id: The channel ID

        Returns:
            Dict[str, Any]: Structured channel data
        """
        # Build basic channel data
        channel_data = {
            "title": channel_info["snippet"]["title"],
            "description": channel_info["snippet"]["description"],
            "custom_url": channel_info["snippet"].get("customUrl", ""),
            "published_at": channel_info["snippet"]["publishedAt"],
            "thumbnails": {size: thumb["url"] for size, thumb in channel_info["snippet"]["thumbnails"].items()},
            "country": channel_info["snippet"].get("country", "Not specified"),
            "channel_id": channel_id,
        }

        # Add statistics if requested
        if self.include_statistics:
            stats = channel_info["statistics"]
            channel_data["statistics"] = {
                "view_count": int(stats.get("viewCount", 0)),
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "hidden_subscriber_count": stats.get("hiddenSubscriberCount", False),
                "video_count": int(stats.get("videoCount", 0)),
            }

        # Add branding information if requested
        if self.include_branding:
            branding = channel_info.get("brandingSettings", {})
            channel_data["branding"] = {
                "title": branding.get("channel", {}).get("title", ""),
                "description": branding.get("channel", {}).get("description", ""),
                "keywords": branding.get("channel", {}).get("keywords", ""),
                "banner_url": branding.get("image", {}).get("bannerExternalUrl", ""),
            }

        # Add playlists if requested
        if self.include_playlists:
            youtube = build("youtube", "v3", developerKey=self.api_key)
            channel_data["playlists"] = self._get_channel_playlists(youtube, channel_id)

        return channel_data
