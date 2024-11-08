import pytube.exceptions
import requests.exceptions
from langchain.tools import StructuredTool
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.document_loaders.youtube import TranscriptFormat
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import IntInput, MultilineInput
from langflow.schema import Data
from langflow.template import Output


class YouTubeTranscriberComponent(LCToolComponent):
    """Component that converts spoken content from YouTube videos into text transcription."""

    display_name = "YouTube Transcriber"
    name = "YoutubeTranscriber"
    description = "Extracts and transcribes spoken content from YouTube videos."
    icon = "Youtube"
    documentation = "https://python.langchain.com/docs/integrations/document_loaders/youtube_transcript/"

    inputs = [
        MultilineInput(name="url", display_name="Video URL", info="Enter the YouTube video URL to transcribe."),
        IntInput(name="chunk_size", display_name="Chunk Size", value=30, info="The Video Chunk Size in seconds."),
    ]

    outputs = [
        Output(name="transcription", display_name="Data", method="build_youtube_transcription"),
        Output(name="transcription_tool", display_name="Tool", method="build_youtube_tool"),
    ]

    class YoutubeApiSchema(BaseModel):
        """Schema to define the input structure for the tool."""

        url: str = Field(..., description="The YouTube URL to transcribe.")

    def build_youtube_transcription(self) -> Data:
        """Method to build transcription from the provided YouTube URL.

        Returns:
            Data: The transcription of the video.
        """
        try:
            # Load the transcription from the provided YouTube URL
            loader = YoutubeLoader.from_youtube_url(
                self.url,  # YouTube video URL
                add_video_info=False,
                transcript_format=TranscriptFormat.CHUNKS,  # Splitting the transcript into chunks
                chunk_size_seconds=self.chunk_size,
            )
        except (
            pytube.exceptions.PytubeError,
            requests.exceptions.RequestException,
            ValueError,
        ) as exc:
            error_msg = f"Failed to transcribe YouTube video: {exc!s}"
            return Data(data={"error": error_msg})
        else:
            # Combine the transcript into one text
            transcription_text = "\n\n".join(map(repr, loader.load()))
            return Data(data={"transcription": transcription_text})

    def youtube_transcription(self, url: str = "") -> dict[str, str]:
        """Helper method to handle transcription outside of component calls.

        Args:
            url: The YouTube URL to transcribe.

        Returns:
            Dict containing either transcription or error message.
        """
        try:
            loader = YoutubeLoader.from_youtube_url(
                url,
                add_video_info=False,
                transcript_format=TranscriptFormat.CHUNKS,
                chunk_size_seconds=self.chunk_size,
            )
        except (
            pytube.exceptions.PytubeError,
            requests.exceptions.RequestException,
            ValueError,
        ) as exc:
            error_msg = f"Failed to transcribe YouTube video: {exc!s}"
            return {"error": error_msg}
        else:
            transcription_text = "\n\n".join(map(repr, loader.load()))
            return {"transcription": transcription_text}

    def build_youtube_tool(self) -> Tool:
        """Method to build the transcription tool.

        Returns:
            Tool: A structured tool that uses the transcription method.

        Raises:
            RuntimeError: If tool creation fails.
        """
        try:
            return StructuredTool.from_function(
                name="youtube_transcription",
                description="Get YouTube video transcriptions when available.",
                func=self.youtube_transcription,
                args_schema=self.YoutubeApiSchema,
            )
        except (
            pytube.exceptions.PytubeError,
            requests.exceptions.RequestException,
            ValueError,
        ) as exc:
            msg = f"Failed to build the YouTube transcription tool: {exc!s}"
            raise RuntimeError(msg) from exc
