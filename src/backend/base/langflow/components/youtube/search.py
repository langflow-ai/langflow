import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from langflow.custom import Component
from langflow.inputs import IntInput, MessageTextInput, SecretStrInput
from langflow.schema import DataFrame
from langflow.template import Output


class YouTubeSearchComponent(Component):
    """A component that searches YouTube and returns a list of video data."""

    display_name: str = "YouTube Search"
    description: str = "Searches YouTube and returns a list of video data based on a query."
    icon: str = "YouTube"
    name = "YouTubeSearch"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Enter the search query for YouTube videos.",
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=5,
            info="The maximum number of video results to return.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="YouTube API Key",
            info="Your YouTube Data API key.",
        ),
    ]

    outputs = [
        Output(name="video_data", display_name="Video Data", method="search_youtube"),
    ]

    def search_youtube(self) -> DataFrame:
        """Searches YouTube and returns video data as a DataFrame."""
        try:
            # Initialize YouTube API client
            youtube = build("youtube", "v3", developerKey=self.api_key)

            # Perform initial search
            search_response = (
                youtube.search()
                .list(q=self.query, type="video", part="id,snippet", maxResults=self.max_results)
                .execute()
            )

            # Prepare data for DataFrame
            video_data_list = []
            for search_result in search_response.get("items", []):
                video_id = search_result["id"]["videoId"]
                snippet = search_result["snippet"]

                video_data = {
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "title": snippet["title"],
                    "description": snippet["description"],
                    "channel_id": snippet["channelId"],
                    "channel_title": snippet["channelTitle"],
                    "published_at": snippet["publishedAt"],
                    "search_query": self.query,
                }

                # Add thumbnails
                thumbnails = snippet["thumbnails"]
                for size, thumb in thumbnails.items():
                    video_data[f"thumbnail_{size}_url"] = thumb["url"]
                    video_data[f"thumbnail_{size}_width"] = thumb.get("width", 0)
                    video_data[f"thumbnail_{size}_height"] = thumb.get("height", 0)

                video_data_list.append(video_data)

            if not video_data_list:
                return DataFrame(pd.DataFrame({"error": ["No results found"]}))

            # Create DataFrame
            video_df = pd.DataFrame(video_data_list)

            # Organize columns in logical groups
            base_cols = [
                "video_id",
                "title",
                "url",
                "channel_id",
                "channel_title",
                "published_at",
                "search_query",
                "description",
            ]

            thumb_cols = sorted([col for col in video_df.columns if col.startswith("thumbnail_")])

            # Get remaining columns that don't fit in any category
            all_defined_cols = base_cols + thumb_cols
            other_cols = [col for col in video_df.columns if col not in all_defined_cols]

            # Combine all columns in desired order
            ordered_cols = base_cols + thumb_cols + other_cols

            # Reorder DataFrame columns
            video_df = video_df[ordered_cols]

            return DataFrame(video_df)

        except HttpError as e:
            return DataFrame(pd.DataFrame({"error": [f"An HTTP error occurred: {e!s}"]}))

        except (KeyError, pd.errors.EmptyDataError) as e:
            return DataFrame(pd.DataFrame({"error": [f"An unexpected error occurred: {e!s}"]}))
