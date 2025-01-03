from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from langflow.custom import Component
from langflow.inputs import IntInput, MessageTextInput, SecretStrInput
from langflow.schema import Data, Message
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

    def search_youtube(self) -> list[Message]:
        """Searches YouTube and returns a list of video data based on the query.

        Returns:
            List[Data]: A list of Data objects, each containing information about a video.
        """
        try:
            youtube = build("youtube", "v3", developerKey=self.api_key)

            search_response = (
                youtube.search()
                .list(q=self.query, type="video", part="id,snippet", maxResults=self.max_results)
                .execute()
            )

            video_data_list = []
            for search_result in search_response.get("items", []):
                video_id = search_result["id"]["videoId"]
                title = search_result["snippet"]["title"]
                description = search_result["snippet"]["description"]
                thumbnail_url = search_result["snippet"]["thumbnails"]["default"]["url"]
                channel_title = search_result["snippet"]["channelTitle"]
                published_at = search_result["snippet"]["publishedAt"]

                video_data = Data(
                    data={
                        "title": title,
                        "video_id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "description": description,
                        "thumbnail_url": thumbnail_url,
                        "channel_title": channel_title,
                        "published_at": published_at,
                    }
                )
                video_data_list.append(video_data)

            if video_data_list:
                self.status = video_data_list
                return video_data_list
            self.status = []
            return []

        except HttpError as e:
            error_data = [Data(data={"error": f"An HTTP error occurred: {e}"})]
            self.status = error_data
            return error_data
        except ValueError as e:
            error_data = [Data(data={"error": f"A value error occurred: {e}"})]
            self.status = error_data
            return error_data
        else:
            self.status = []
            return []
