import googleapiclient
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from langflow.custom import Component
from langflow.inputs import BoolInput, MessageTextInput, SecretStrInput
from langflow.schema import Data
from langflow.template import Output


class YouTubeVideoDetailsComponent(Component):
    """A component that retrieves detailed information about YouTube videos."""

    display_name: str = "YouTube Video Details"
    description: str = "Retrieves detailed information and statistics about YouTube videos."
    icon: str = "YouTube"
    name = "YouTubeVideoDetails"

    inputs = [
        MessageTextInput(
            name="video_url",
            display_name="Video URL",
            info="The URL of the YouTube video.",
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
            info="Include video statistics (views, likes, comments).",
        ),
        BoolInput(
            name="include_content_details",
            display_name="Include Content Details",
            value=True,
            info="Include video duration, quality, and age restriction info.",
            advanced=True,
        ),
        BoolInput(
            name="include_tags",
            display_name="Include Tags",
            value=True,
            info="Include video tags and keywords.",
            advanced=True,
        ),
        BoolInput(
            name="include_thumbnails",
            display_name="Include Thumbnails",
            value=True,
            info="Include video thumbnail URLs in different resolutions.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="video_data", display_name="Video Data", method="get_video_details"),
    ]

    API_FORBIDDEN = 403
    VIDEO_NOT_FOUND = 404

    def _extract_video_id(self, video_url: str) -> str:
        """Extracts the video ID from a YouTube URL.

        Args:
            video_url (str): The URL of the YouTube video

        Returns:
            str: The video ID
        """
        import re

        # Regular expressions for different YouTube URL formats
        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu.be\/|youtube.com\/embed\/)([^&\n?#]+)",
            r"youtube.com\/shorts\/([^&\n?#]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)

        # If no patterns match, assume the input might be the video ID itself
        return video_url.strip()

    def _format_duration(self, duration: str) -> str:
        """Formats the ISO 8601 duration to a readable format.

        Args:
            duration (str): ISO 8601 duration string

        Returns:
            str: Formatted duration string
        """
        import re

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

        # Format the duration string
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _get_video_quality_info(self, content_details: dict) -> dict:
        """Extracts video quality information.

        Args:
            content_details (Dict): Video content details from API

        Returns:
            Dict: Formatted video quality information
        """
        return {
            "definition": content_details.get("definition", "unknown").upper(),
            "dimension": content_details.get("dimension", "2d"),
            "has_caption": content_details.get("caption", "false") == "true",
            "projection": content_details.get("projection", "rectangular"),
        }

    def get_video_details(self) -> Data:
        """Retrieves detailed information about a YouTube video.

        Returns:
            Data: A Data object containing video information
        """
        try:
            # Extract video ID from URL
            video_id = self._extract_video_id(self.video_url)

            # Initialize YouTube API client
            youtube = build("youtube", "v3", developerKey=self.api_key)

            # Prepare parts for the API request
            parts = ["snippet"]
            if self.include_statistics:
                parts.append("statistics")
            if self.include_content_details:
                parts.append("contentDetails")

            # Get video information
            video_response = youtube.videos().list(part=",".join(parts), id=video_id).execute()

            if not video_response["items"]:
                return Data(data={"error": "Video not found"})

            video_info = video_response["items"][0]
            snippet = video_info["snippet"]

            # Build basic video data
            video_data = {
                "title": snippet["title"],
                "description": snippet["description"],
                "published_at": snippet["publishedAt"],
                "channel_id": snippet["channelId"],
                "channel_title": snippet["channelTitle"],
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "category_id": snippet.get("categoryId", "Unknown"),
                "live_broadcast_content": snippet.get("liveBroadcastContent", "none"),
            }

            # Add thumbnails if requested
            if self.include_thumbnails:
                video_data["thumbnails"] = {
                    size: {"url": thumb["url"], "width": thumb.get("width", 0), "height": thumb.get("height", 0)}
                    for size, thumb in snippet["thumbnails"].items()
                }

            # Add tags if requested and available
            if self.include_tags and "tags" in snippet:
                video_data["tags"] = snippet["tags"]

            # Add statistics if requested
            if self.include_statistics and "statistics" in video_info:
                stats = video_info["statistics"]
                video_data["statistics"] = {
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "favorite_count": int(stats.get("favoriteCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                }

            # Add content details if requested
            if self.include_content_details and "contentDetails" in video_info:
                content_details = video_info["contentDetails"]
                video_data["content_details"] = {
                    "duration": self._format_duration(content_details["duration"]),
                    "dimension": content_details.get("dimension", "2d"),
                    "definition": content_details.get("definition", "hd").upper(),
                    "caption": content_details.get("caption", "false") == "true",
                    "licensed_content": content_details.get("licensedContent", False),
                    "projection": content_details.get("projection", "rectangular"),
                    "has_custom_thumbnails": content_details.get("hasCustomThumbnail", False),
                }

                # Add age restriction info if present
                if "contentRating" in content_details:
                    video_data["content_details"]["content_rating"] = content_details["contentRating"]

            self.status = video_data
            return Data(data=video_data)

        except HttpError as e:
            error_message = f"YouTube API error: {e!s}"
            if e.resp.status == self.API_FORBIDDEN:
                error_message = "API quota exceeded or access forbidden."
            elif e.resp.status == self.VIDEO_NOT_FOUND:
                error_message = "Video not found."

            error_data = {"error": error_message}
            self.status = error_data
            return Data(data=error_data)

        except googleapiclient.errors.HttpError as e:
            error_message = f"YouTube API error: {e!s}"
            if e.resp.status == self.API_FORBIDDEN:
                error_message = "API quota exceeded or access forbidden."
            elif e.resp.status == self.VIDEO_NOT_FOUND:
                error_message = "Video not found."

            error_data = {"error": error_message}
            self.status = error_data
            return Data(data=error_data)
