from lfx.custom.custom_component.component import Component
from pytube import Playlist  # Ensure you have pytube installed

from langflow.inputs.inputs import MessageTextInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.template.field.base import Output


class YouTubePlaylistComponent(Component):
    display_name = "Youtube Playlist"
    description = "Extracts all video URLs from a YouTube playlist."
    icon = "YouTube"  # Replace with a suitable icon

    inputs = [
        MessageTextInput(
            name="playlist_url",
            display_name="Playlist URL",
            info="URL of the YouTube playlist.",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Video URLs", name="video_urls", method="extract_video_urls"),
    ]

    def extract_video_urls(self) -> DataFrame:
        playlist_url = self.playlist_url
        playlist = Playlist(playlist_url)
        video_urls = [video.watch_url for video in playlist.videos]

        return DataFrame([Data(data={"video_url": url}) for url in video_urls])
