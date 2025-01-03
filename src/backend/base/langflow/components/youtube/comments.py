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


class YouTubeCommentsComponent(Component):
    """A component that retrieves comments from YouTube videos."""

    display_name: str = "YouTube Comments"
    description: str = "Retrieves and analyzes comments from YouTube videos."
    icon: str = "YouTube"
    name = "YouTubeComments"

    # Constants
    COMMENTS_DISABLED_STATUS = 403
    NOT_FOUND_STATUS = 404
    API_MAX_RESULTS = 100

    inputs = [
        MessageTextInput(
            name="video_url",
            display_name="Video URL",
            info="The URL of the YouTube video to get comments from.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="YouTube API Key",
            info="Your YouTube Data API key.",
            required=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=20,
            info="The maximum number of comments to return.",
        ),
        DropdownInput(
            name="sort_by",
            display_name="Sort By",
            options=["time", "relevance"],
            value="relevance",
            info="Sort comments by time or relevance.",
        ),
        BoolInput(
            name="include_replies",
            display_name="Include Replies",
            value=False,
            info="Whether to include replies to comments.",
            advanced=True,
        ),
        BoolInput(
            name="include_metrics",
            display_name="Include Metrics",
            value=True,
            info="Include metrics like like count and reply count.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="comments", display_name="Comments", method="get_video_comments"),
    ]

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

    def _process_reply(self, reply: dict, *, include_metrics: bool = True) -> dict:
        """Process a single reply comment.

        Args:
            reply (dict): Raw reply data from API
            include_metrics (bool): Whether to include metrics

        Returns:
            dict: Processed reply data
        """
        reply_snippet = reply["snippet"]
        reply_data = {
            "author": reply_snippet["authorDisplayName"],
            "text": reply_snippet["textDisplay"],
            "published_at": reply_snippet["publishedAt"],
        }
        if include_metrics:
            reply_data["like_count"] = reply_snippet["likeCount"]
        return reply_data

    def _process_comment(self, item: dict, *, include_metrics: bool = True, include_replies: bool = False) -> dict:
        """Process a single comment thread.

        Args:
            item (dict): Raw comment thread data from API
            include_metrics (bool): Whether to include metrics
            include_replies (bool): Whether to include replies

        Returns:
            dict: Processed comment data
        """
        comment = item["snippet"]["topLevelComment"]["snippet"]

        # Basic comment data
        comment_data = {
            "author": comment["authorDisplayName"],
            "author_channel_url": comment.get("authorChannelUrl", ""),
            "text": comment["textDisplay"],
            "published_at": comment["publishedAt"],
            "updated_at": comment["updatedAt"],
        }

        # Add metrics if requested
        if include_metrics:
            comment_data.update(
                {
                    "like_count": comment["likeCount"],
                    "reply_count": item["snippet"]["totalReplyCount"],
                }
            )

        # Add replies if requested
        if include_replies and item["snippet"]["totalReplyCount"] > 0 and "replies" in item:
            comment_data["replies"] = [
                self._process_reply(reply, include_metrics=include_metrics) for reply in item["replies"]["comments"]
            ]

        return comment_data

    def get_video_comments(self) -> list[Data]:
        """Retrieves comments from a YouTube video.

        Returns:
            List[Data]: A list of Data objects containing comment information
        """
        try:
            # Extract video ID from URL
            video_id = self._extract_video_id(self.video_url)

            # Initialize YouTube API client
            youtube = build("youtube", "v3", developerKey=self.api_key)

            # Prepare the initial request
            request = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=min(self.API_MAX_RESULTS, self.max_results),
                order=self.sort_by,
                textFormat="plainText",
            )

            comments_data = []
            results_count = 0

            while request and results_count < self.max_results:
                response = request.execute()

                for item in response.get("items", []):
                    if results_count >= self.max_results:
                        break

                    comment_data = self._process_comment(
                        item, include_metrics=self.include_metrics, include_replies=self.include_replies
                    )
                    comments_data.append(Data(data=comment_data))
                    results_count += 1

                # Get the next page if available and needed
                if "nextPageToken" in response and results_count < self.max_results:
                    request = youtube.commentThreads().list(
                        part="snippet,replies",
                        videoId=video_id,
                        maxResults=min(self.API_MAX_RESULTS, self.max_results - results_count),
                        order=self.sort_by,
                        textFormat="plainText",
                        pageToken=response["nextPageToken"],
                    )
                else:
                    request = None

        except HttpError as e:
            error_message = f"YouTube API error: {e!s}"
            if e.resp.status == self.COMMENTS_DISABLED_STATUS:
                error_message = "Comments are disabled for this video or API quota exceeded."
            elif e.resp.status == self.NOT_FOUND_STATUS:
                error_message = "Video not found."

            error_data = [Data(data={"error": error_message})]
            self.status = error_data
            return error_data

        except (ValueError, KeyError, AttributeError) as e:
            error_msg = f"Error processing comment data: {e!s}"
            error_data = [Data(data={"error": error_msg})]
            self.status = error_data
            return error_data

        except (ConnectionError, TimeoutError) as e:
            error_msg = f"Network error: {e!s}"
            error_data = [Data(data={"error": error_msg})]
            self.status = error_data
            return error_data

        self.status = comments_data
        return comments_data
