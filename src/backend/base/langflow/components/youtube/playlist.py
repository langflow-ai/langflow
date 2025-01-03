from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from langflow.custom import Component
from langflow.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.schema import Data
from langflow.template import Output


class YouTubeError(Exception):
    """Base exception class for YouTube-related errors."""


class YouTubeAPIError(YouTubeError):
    """Exception raised for YouTube API-related errors."""


class YouTubePlaylistComponent(Component):
    """A component that retrieves and analyzes YouTube playlists."""

    display_name: str = "YouTube Playlist"
    description: str = "Retrieves and analyzes YouTube playlist information and videos."
    icon: str = "YouTube"
    name = "YouTubePlaylist"

    # Constants
    PLAYLIST_ID_MIN_LENGTH = 12
    MINUTES_SECONDS_PARTS = 2
    HOURS_MINUTES_SECONDS_PARTS = 3
    SECONDS_PER_MINUTE = 60
    SECONDS_PER_HOUR = 3600
    QUOTA_EXCEEDED_STATUS = 403
    NOT_FOUND_STATUS = 404
    MAX_RESULTS_PER_PAGE = 50

    inputs = [
        MessageTextInput(
            name="playlist_url",
            display_name="Playlist URL or ID",
            info="The URL or ID of the YouTube playlist.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="YouTube API Key",
            info="Your YouTube Data API key.",
            required=True,
        ),
        IntInput(
            name="max_videos",
            display_name="Max Videos",
            value=50,
            info="Maximum number of videos to retrieve from the playlist (1-500).",
        ),
        BoolInput(
            name="include_video_details",
            display_name="Include Video Details",
            value=True,
            info="Include detailed information about each video.",
        ),
        BoolInput(
            name="include_statistics",
            display_name="Include Statistics",
            value=True,
            info="Include playlist and video statistics.",
        ),
        DropdownInput(
            name="sort_order",
            display_name="Sort Order",
            options=["position", "date", "rating", "title"],
            value="position",
            info="Sort order for playlist videos.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="playlist_data", display_name="Playlist Data", method="get_playlist_info"),
    ]

    def _extract_playlist_id(self, playlist_url: str) -> str:
        """Extracts the playlist ID from various YouTube playlist URL formats.

        Args:
            playlist_url (str): The URL or ID of the YouTube playlist

        Returns:
            str: The playlist ID
        """
        import re

        # If it's already a playlist ID
        if playlist_url.startswith("PL") and len(playlist_url) > self.PLAYLIST_ID_MIN_LENGTH:
            return playlist_url

        # Regular expressions for different playlist URL formats
        patterns = [
            r"[?&]list=([^&\s]+)",  # Standard format
            r"youtube\.com/playlist\?.*list=([^&\s]+)",  # Playlist page
            r"youtube\.com/watch\?.*list=([^&\s]+)",  # Video in playlist
        ]

        for pattern in patterns:
            match = re.search(pattern, playlist_url)
            if match:
                return match.group(1)

        return playlist_url.strip()

    def _format_duration(self, duration: str) -> str:
        """Formats ISO 8601 duration to readable format."""
        import re

        # Remove PT from start
        duration = duration.replace("PT", "")

        # Initialize hours, minutes, seconds
        hours = 0
        minutes = 0
        seconds = 0

        # Extract hours, minutes, and seconds
        hours_match = re.search(r"(\d+)H", duration)
        minutes_match = re.search(r"(\d+)M", duration)
        seconds_match = re.search(r"(\d+)S", duration)

        if hours_match:
            hours = int(hours_match.group(1))
        if minutes_match:
            minutes = int(minutes_match.group(1))
        if seconds_match:
            seconds = int(seconds_match.group(1))

        # Format output
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _sort_videos(self, videos: list[dict], sort_order: str) -> list[dict]:
        """Sorts the video list based on the specified order."""
        if sort_order == "position":
            return sorted(videos, key=lambda x: x.get("position", 0))
        if sort_order == "date":
            return sorted(videos, key=lambda x: x.get("published_at", ""), reverse=True)
        if sort_order == "rating":
            return sorted(
                videos,
                key=lambda x: (int(x.get("statistics", {}).get("like_count", 0)) if "statistics" in x else 0),
                reverse=True,
            )
        if sort_order == "title":
            return sorted(videos, key=lambda x: x.get("title", "").lower())
        return videos

    def _calculate_total_duration(self, videos: list[dict]) -> str:
        """Calculate total duration of all videos in the playlist."""
        total_seconds = 0
        for video in videos:
            if "duration" in video:
                parts = video["duration"].split(":")
                if len(parts) == self.MINUTES_SECONDS_PARTS:  # MM:SS
                    total_seconds += int(parts[0]) * self.SECONDS_PER_MINUTE + int(parts[1])
                elif len(parts) == self.HOURS_MINUTES_SECONDS_PARTS:  # HH:MM:SS
                    total_seconds += (
                        int(parts[0]) * self.SECONDS_PER_HOUR + int(parts[1]) * self.SECONDS_PER_MINUTE + int(parts[2])
                    )

        hours = total_seconds // self.SECONDS_PER_HOUR
        minutes = (total_seconds % self.SECONDS_PER_HOUR) // self.SECONDS_PER_MINUTE
        return f"{hours}h {minutes}m"

    def get_playlist_info(self) -> Data:
        """Retrieves detailed information about a YouTube playlist and its videos.

        Returns:
            Data: A Data object containing playlist information and videos
        """
        try:
            # Extract playlist ID
            playlist_id = self._extract_playlist_id(self.playlist_url)

            # Initialize YouTube API client
            youtube = build("youtube", "v3", developerKey=self.api_key)

            # Get playlist details
            playlist_response = (
                youtube.playlists().list(part="snippet,status,contentDetails,player", id=playlist_id).execute()
            )

            if not playlist_response["items"]:
                error_data = {"error": "Playlist not found"}
                self.status = error_data
                return Data(data=error_data)

            playlist_info = playlist_response["items"][0]

            # Build basic playlist data
            playlist_data = {
                "playlist_id": playlist_id,
                "title": playlist_info["snippet"]["title"],
                "description": playlist_info["snippet"]["description"],
                "channel_id": playlist_info["snippet"]["channelId"],
                "channel_title": playlist_info["snippet"]["channelTitle"],
                "published_at": playlist_info["snippet"]["publishedAt"],
                "privacy_status": playlist_info["status"]["privacyStatus"],
                "video_count": playlist_info["contentDetails"]["itemCount"],
                "thumbnails": playlist_info["snippet"]["thumbnails"],
                "videos": [],
            }

            # Get videos in playlist
            playlist_data["videos"] = self._fetch_playlist_videos(youtube, playlist_id)

            # Sort videos based on specified order
            playlist_data["videos"] = self._sort_videos(playlist_data["videos"], self.sort_order)

            # Calculate total duration if video details were requested
            if self.include_video_details:
                playlist_data["total_duration"] = self._calculate_total_duration(playlist_data["videos"])

            self.status = playlist_data
            return Data(data=playlist_data)

        except HttpError as e:
            if e.resp.status == self.QUOTA_EXCEEDED_STATUS:
                error_message = "API quota exceeded or access forbidden."
            elif e.resp.status == self.NOT_FOUND_STATUS:
                error_message = "Playlist not found."
            else:
                error_message = f"YouTube API error: {e!s}"

            error_data = {"error": error_message}
            self.status = error_data
            return Data(data=error_data)

        except (ValueError, KeyError, AttributeError) as e:
            error_msg = f"Error processing playlist data: {e!s}"
            error_data = {"error": error_msg}
            self.status = error_data
            return Data(data=error_data)

        except (ConnectionError, TimeoutError) as e:
            error_msg = f"Network error: {e!s}"
            error_data = {"error": error_msg}
            self.status = error_data
            return Data(data=error_data)

    def _fetch_playlist_videos(self, youtube, playlist_id: str) -> list[dict]:
        """Fetches videos from a playlist.

        Args:
            youtube: YouTube API client
            playlist_id: ID of the playlist

        Returns:
            list[dict]: List of video information
        """
        videos = []
        next_page_token = None
        total_videos = 0

        while total_videos < self.max_videos:
            # Get playlist items
            playlist_items = (
                youtube.playlistItems()
                .list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=min(self.MAX_RESULTS_PER_PAGE, self.max_videos - total_videos),
                    pageToken=next_page_token,
                )
                .execute()
            )

            if not playlist_items.get("items"):
                break

            video_ids = [item["contentDetails"]["videoId"] for item in playlist_items["items"]]

            # Get detailed video information if requested
            if self.include_video_details:
                videos.extend(self._get_detailed_video_info(youtube, video_ids, playlist_items["items"]))
            else:
                videos.extend(self._get_basic_video_info(playlist_items["items"]))

            total_videos += len(playlist_items["items"])
            next_page_token = playlist_items.get("nextPageToken")

            if not next_page_token:
                break

        return videos

    def _get_detailed_video_info(self, youtube, video_ids: list[str], playlist_items: list[dict]) -> list[dict]:
        """Gets detailed information for a list of videos.

        Args:
            youtube: YouTube API client
            video_ids: List of video IDs
            playlist_items: List of playlist items

        Returns:
            list[dict]: List of detailed video information
        """
        parts = ["snippet", "contentDetails"]
        if self.include_statistics:
            parts.append("statistics")

        video_response = youtube.videos().list(part=",".join(parts), id=",".join(video_ids)).execute()

        videos = []
        for playlist_item in playlist_items:
            video_id = playlist_item["contentDetails"]["videoId"]
            video_info = next((v for v in video_response.get("items", []) if v["id"] == video_id), None)

            if video_info:
                video_data = self._build_video_data(video_info, playlist_item, include_details=True)
                videos.append(video_data)

        return videos

    def _get_basic_video_info(self, playlist_items: list[dict]) -> list[dict]:
        """Gets basic information for playlist items.

        Args:
            playlist_items: List of playlist items

        Returns:
            list[dict]: List of basic video information
        """
        return [self._build_video_data(None, item, include_details=False) for item in playlist_items]

    def _build_video_data(self, video_info: dict | None, playlist_item: dict, *, include_details: bool) -> dict:
        """Builds video data dictionary.

        Args:
            video_info: Detailed video information (optional)
            playlist_item: Basic playlist item information
            include_details: Whether to include detailed information

        Returns:
            dict: Video data dictionary
        """
        video_id = playlist_item["contentDetails"]["videoId"]

        if include_details and video_info:
            video_data = {
                "video_id": video_id,
                "title": video_info["snippet"]["title"],
                "description": video_info["snippet"]["description"],
                "position": playlist_item["snippet"]["position"],
                "published_at": video_info["snippet"]["publishedAt"],
                "thumbnails": video_info["snippet"]["thumbnails"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }

            if "contentDetails" in video_info:
                video_data["duration"] = self._format_duration(video_info["contentDetails"]["duration"])

            if self.include_statistics and "statistics" in video_info:
                video_data["statistics"] = {
                    "view_count": int(video_info["statistics"].get("viewCount", 0)),
                    "like_count": int(video_info["statistics"].get("likeCount", 0)),
                    "comment_count": int(video_info["statistics"].get("commentCount", 0)),
                }
        else:
            video_data = {
                "video_id": video_id,
                "title": playlist_item["snippet"]["title"],
                "description": playlist_item["snippet"]["description"],
                "position": playlist_item["snippet"]["position"],
                "published_at": playlist_item["snippet"]["publishedAt"],
                "thumbnails": playlist_item["snippet"]["thumbnails"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }

        return video_data
