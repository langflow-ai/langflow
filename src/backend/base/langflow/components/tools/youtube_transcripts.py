from langchain.tools import StructuredTool
from langchain_community.document_loaders import YoutubeLoader
from langchain_community.document_loaders.youtube import TranscriptFormat
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import DropdownInput, IntInput, MultilineInput
from langflow.schema import Data
from langflow.template import Output


class YoutubeApiSchema(BaseModel):
    """Schema to define the input structure for the tool."""

    url: str = Field(..., description="The YouTube URL to get transcripts from.")
    transcript_format: TranscriptFormat = Field(
        TranscriptFormat.TEXT,
        description="The format of the transcripts. Either 'text' for a single "
        "text output or 'chunks' for timestamped chunks.",
    )
    chunk_size_seconds: int = Field(
        120,
        description="The size of each transcript chunk in seconds. Only "
        "applicable when 'Transcript Format' is set to 'chunks'.",
    )
    language: str = Field(
        "",
        description="A comma-separated list of language codes in descending " "priority. Leave empty for default.",
    )
    translation: str = Field(
        "", description="Translate the transcripts to the specified language. " "Leave empty for no translation."
    )


class YouTubeTranscriptsComponent(LCToolComponent):
    """A component that extracts spoken content from YouTube videos as transcripts."""

    display_name: str = "YouTube Transcripts"
    description: str = "Extracts spoken content from YouTube videos as transcripts."
    icon: str = "YouTube"

    inputs = [
        MultilineInput(
            name="url", display_name="Video URL", info="Enter the YouTube video URL to get transcripts from."
        ),
        DropdownInput(
            name="transcript_format",
            display_name="Transcript Format",
            options=["text", "chunks"],
            value="text",
            info="The format of the transcripts. Either 'text' for a single output "
            "or 'chunks' for timestamped chunks.",
        ),
        IntInput(
            name="chunk_size_seconds",
            display_name="Chunk Size (seconds)",
            value=60,
            advanced=True,
            info="The size of each transcript chunk in seconds. Only applicable when "
            "'Transcript Format' is set to 'chunks'.",
        ),
        MultilineInput(
            name="language",
            display_name="Language",
            info="A comma-separated list of language codes in descending priority. " "Leave empty for default.",
        ),
        DropdownInput(
            name="translation",
            display_name="Translation Language",
            advanced=True,
            options=["", "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "hi", "ar", "id"],
            info="Translate the transcripts to the specified language. " "Leave empty for no translation.",
        ),
    ]

    outputs = [
        Output(name="transcripts", display_name="Data", method="build_youtube_transcripts"),
        Output(name="transcripts_tool", display_name="Tool", method="build_youtube_tool"),
    ]

    def build_youtube_transcripts(self) -> Data | list[Data]:
        """Method to build transcripts from the provided YouTube URL.

        Returns:
            Data | list[Data]: The transcripts of the video, either as a single
            Data object or a list of Data objects.
        """
        try:
            loader = YoutubeLoader.from_youtube_url(
                self.url,
                transcript_format=TranscriptFormat.TEXT
                if self.transcript_format == "text"
                else TranscriptFormat.CHUNKS,
                chunk_size_seconds=self.chunk_size_seconds,
                language=self.language.split(",") if self.language else ["en"],
                translation=self.translation if self.translation else None,
            )

            transcripts = loader.load()

            if self.transcript_format == "text":
                # Extract only the page_content from the Document
                return Data(data={"transcripts": transcripts[0].page_content})
            # For chunks, extract page_content and metadata separately
            return [Data(data={"content": doc.page_content, "metadata": doc.metadata}) for doc in transcripts]

        except Exception as exc:  # noqa: BLE001
            # Using a specific error type for the return value
            return Data(data={"error": f"Failed to get YouTube transcripts: {exc!s}"})

    def youtube_transcripts(
        self,
        url: str = "",
        transcript_format: TranscriptFormat = TranscriptFormat.TEXT,
        chunk_size_seconds: int = 120,
        language: str = "",
        translation: str = "",
    ) -> Data | list[Data]:
        """Helper method to handle transcripts outside of component calls.

        Args:
            url: The YouTube URL to get transcripts from.
            transcript_format: Format of transcripts ('text' or 'chunks').
            chunk_size_seconds: Size of each transcript chunk in seconds.
            language: Comma-separated list of language codes.
            translation: Target language for translation.

        Returns:
            Data | list[Data]: Video transcripts as single Data or list of Data.
        """
        try:
            if isinstance(transcript_format, str):
                transcript_format = TranscriptFormat(transcript_format)
            loader = YoutubeLoader.from_youtube_url(
                url,
                transcript_format=TranscriptFormat.TEXT
                if transcript_format == TranscriptFormat.TEXT
                else TranscriptFormat.CHUNKS,
                chunk_size_seconds=chunk_size_seconds,
                language=language.split(",") if language else ["en"],
                translation=translation if translation else None,
            )

            transcripts = loader.load()
            if transcript_format == TranscriptFormat.TEXT and len(transcripts) > 0:
                return Data(data={"transcript": transcripts[0].page_content})
            return [Data(data={"content": doc.page_content, "metadata": doc.metadata}) for doc in transcripts]
        except Exception as exc:
            msg = f"Failed to get YouTube transcripts: {exc!s}"
            raise ToolException(msg) from exc

    def build_youtube_tool(self) -> Tool:
        """Method to build the transcripts tool.

        Returns:
            Tool: A structured tool that uses the transcripts method.

        Raises:
            RuntimeError: If tool creation fails.
        """
        try:
            return StructuredTool.from_function(
                name="youtube_transcripts",
                description="Get transcripts from YouTube videos.",
                func=self.youtube_transcripts,
                args_schema=YoutubeApiSchema,
            )

        except Exception as exc:
            msg = f"Failed to build the YouTube transcripts tool: {exc!s}"
            raise RuntimeError(msg) from exc
