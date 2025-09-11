from contextlib import contextmanager

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.schema.dataframe import DataFrame
from langflow.template.field.base import Output


class YouTubeCommentsComponent(Component):
    """A component that retrieves comments from YouTube videos."""

    display_name: str = "YouTube Comments"
    description: str = "Retrieves and analyzes comments from YouTube videos."
    icon: str = "YouTube"

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
            required=True,
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
        """Extracts the video ID from a YouTube URL."""
        import re

        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu.be\/|youtube.com\/embed\/)([^&\n?#]+)",
            r"youtube.com\/shorts\/([^&\n?#]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)

        return video_url.strip()

    def _process_reply(self, reply: dict, parent_id: str, *, include_metrics: bool = True) -> dict:
        """Process a single reply comment."""
        reply_snippet = reply["snippet"]
        reply_data = {
            "comment_id": reply["id"],
            "parent_comment_id": parent_id,
            "author": reply_snippet["authorDisplayName"],
            "text": reply_snippet["textDisplay"],
            "published_at": reply_snippet["publishedAt"],
            "is_reply": True,
        }
        if include_metrics:
            reply_data["like_count"] = reply_snippet["likeCount"]
            reply_data["reply_count"] = 0  # Replies can't have replies

        return reply_data

    def _process_comment(
        self, item: dict, *, include_metrics: bool = True, include_replies: bool = False
    ) -> list[dict]:
        """Process a single comment thread."""
        comment = item["snippet"]["topLevelComment"]["snippet"]
        comment_id = item["snippet"]["topLevelComment"]["id"]

        # Basic comment data
        processed_comments = [
            {
                "comment_id": comment_id,
                "parent_comment_id": "",  # Empty for top-level comments
                "author": comment["authorDisplayName"],
                "author_channel_url": comment.get("authorChannelUrl", ""),
                "text": comment["textDisplay"],
                "published_at": comment["publishedAt"],
                "updated_at": comment["updatedAt"],
                "is_reply": False,
            }
        ]

        # Add metrics if requested
        if include_metrics:
            processed_comments[0].update(
                {
                    "like_count": comment["likeCount"],
                    "reply_count": item["snippet"]["totalReplyCount"],
                }
            )

        # Add replies if requested
        if include_replies and item["snippet"]["totalReplyCount"] > 0 and "replies" in item:
            for reply in item["replies"]["comments"]:
                reply_data = self._process_reply(reply, parent_id=comment_id, include_metrics=include_metrics)
                processed_comments.append(reply_data)

        return processed_comments

    @contextmanager
    def youtube_client(self):
        """Context manager for YouTube API client."""
        client = build("youtube", "v3", developerKey=self.api_key)
        try:
            yield client
        finally:
            client.close()

    def get_video_comments(self) -> DataFrame:
        """Retrieves comments from a YouTube video and returns as DataFrame."""
        try:
            # Extract video ID from URL
            video_id = self._extract_video_id(self.video_url)

            # Use context manager for YouTube API client
            with self.youtube_client() as youtube:
                comments_data = []
                results_count = 0
                request = youtube.commentThreads().list(
                    part="snippet,replies",
                    videoId=video_id,
                    maxResults=min(self.API_MAX_RESULTS, self.max_results),
                    order=self.sort_by,
                    textFormat="plainText",
                )

                while request and results_count < self.max_results:
                    response = request.execute()

                    for item in response.get("items", []):
                        if results_count >= self.max_results:
                            break

                        comments = self._process_comment(
                            item, include_metrics=self.include_metrics, include_replies=self.include_replies
                        )
                        comments_data.extend(comments)
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

                # Convert to DataFrame
                comments_df = pd.DataFrame(comments_data)

                # Add video metadata
                comments_df["video_id"] = video_id
                comments_df["video_url"] = self.video_url

                # Sort columns for better organization
                column_order = [
                    "video_id",
                    "video_url",
                    "comment_id",
                    "parent_comment_id",
                    "is_reply",
                    "author",
                    "author_channel_url",
                    "text",
                    "published_at",
                    "updated_at",
                ]

                if self.include_metrics:
                    column_order.extend(["like_count", "reply_count"])

                comments_df = comments_df[column_order]

                return DataFrame(comments_df)

        except HttpError as e:
            error_message = f"YouTube API error: {e!s}"
            if e.resp.status == self.COMMENTS_DISABLED_STATUS:
                error_message = "Comments are disabled for this video or API quota exceeded."
            elif e.resp.status == self.NOT_FOUND_STATUS:
                error_message = "Video not found."

            return DataFrame(pd.DataFrame({"error": [error_message]}))
