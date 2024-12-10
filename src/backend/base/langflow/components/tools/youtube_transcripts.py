from langchain_community.document_loaders import YoutubeLoader
from langchain_community.document_loaders.youtube import TranscriptFormat

from langflow.custom import Component
from langflow.inputs import DropdownInput, IntInput, MultilineInput
from langflow.schema import Data
from langflow.template import Output


class YouTubeTranscriptsComponent(Component):
    """A component that extracts spoken content from YouTube videos as transcripts."""

    display_name: str = "YouTube Transcripts"
    description: str = "Extracts spoken content from YouTube videos as transcripts."
    icon: str = "YouTube"
    name = "YouTubeTranscripts"

    inputs = [
        MultilineInput(
            name="url",
            display_name="Video URL",
            info="Enter the YouTube video URL to get transcripts from.",
            tool_mode=True,
        ),
        DropdownInput(
            name="transcript_format",
            display_name="Transcript Format",
            options=["text", "chunks"],
            value="text",
            info="The format of the transcripts. Either 'text' for a single output "
            "or 'chunks' for timestamped chunks.",
            advanced=True,
        ),
        IntInput(
            name="chunk_size_seconds",
            display_name="Chunk Size (seconds)",
            value=60,
            advanced=True,
            info="The size of each transcript chunk in seconds. Only applicable when "
            "'Transcript Format' is set to 'chunks'.",
        ),
        DropdownInput(
            name="language",
            display_name="Language",
            options=[
                "af",
                "ak",
                "sq",
                "am",
                "ar",
                "hy",
                "as",
                "ay",
                "az",
                "bn",
                "eu",
                "be",
                "bho",
                "bs",
                "bg",
                "my",
                "ca",
                "ceb",
                "zh",
                "zh-HK",
                "zh-CN",
                "zh-SG",
                "zh-TW",
                "zh-Hans",
                "zh-Hant",
                "hak-TW",
                "nan-TW",
                "co",
                "hr",
                "cs",
                "da",
                "dv",
                "nl",
                "en",
                "en-US",
                "eo",
                "et",
                "ee",
                "fil",
                "fi",
                "fr",
                "gl",
                "lg",
                "ka",
                "de",
                "el",
                "gn",
                "gu",
                "ht",
                "ha",
                "haw",
                "iw",
                "hi",
                "hmn",
                "hu",
                "is",
                "ig",
                "id",
                "ga",
                "it",
                "ja",
                "jv",
                "kn",
                "kk",
                "km",
                "rw",
                "ko",
                "kri",
                "ku",
                "ky",
                "lo",
                "la",
                "lv",
                "ln",
                "lt",
                "lb",
                "mk",
                "mg",
                "ms",
                "ml",
                "mt",
                "mi",
                "mr",
                "mn",
                "ne",
                "nso",
                "no",
                "ny",
                "or",
                "om",
                "ps",
                "fa",
                "pl",
                "pt",
                "pa",
                "qu",
                "ro",
                "ru",
                "sm",
                "sa",
                "gd",
                "sr",
                "sn",
                "sd",
                "si",
                "sk",
                "sl",
                "so",
                "st",
                "es",
                "su",
                "sw",
                "sv",
                "tg",
                "ta",
                "tt",
                "te",
                "th",
                "ti",
                "ts",
                "tr",
                "tk",
                "uk",
                "ur",
                "ug",
                "uz",
                "vi",
                "cy",
                "fy",
                "xh",
                "yi",
                "yo",
                "zu",
            ],
            value="en",
            info=(
                "Specify to make sure the transcripts are retrieved in your desired language. "
                "Defaults to English: 'en'"
            ),
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
                language=[self.language],
                translation=self.translation or None,
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
