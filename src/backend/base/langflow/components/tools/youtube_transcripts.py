from langchain_community.document_loaders import YoutubeLoader
from langchain_community.document_loaders.youtube import TranscriptFormat

from langflow.custom import Component
from langflow.inputs import DropdownInput, IntInput, MultilineInput
from langflow.schema import Message
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
            info="The format of the transcripts. Either 'text' for a single output or 'chunks' for timestamped chunks.",
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
                "Specify to make sure the transcripts are retrieved in your desired language. Defaults to English: 'en'"
            ),
        ),
        DropdownInput(
            name="translation",
            display_name="Translation Language",
            advanced=True,
            options=["", "en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "hi", "ar", "id"],
            info="Translate the transcripts to the specified language. Leave empty for no translation.",
        ),
    ]

    outputs = [
        Output(name="transcripts", display_name="Transcription", method="build_youtube_transcripts"),
    ]

    def build_youtube_transcripts(self) -> Message:
        """Method to extracts transcripts from a YouTube video URL.

        Returns:
            Message: The transcripts of the video as a text string. If 'transcript_format'
            is 'text', the transcripts are returned as a single continuous string. If
            'transcript_format' is 'chunks', the transcripts are returned as a string
            with timestamped segments.

        Raises:
            Exception: Returns an error message if transcript retrieval fails.
        """
        try:
            # Attempt to load transcripts in the specified language, fallback to any available language
            languages = [self.language] if self.language else None
            loader = YoutubeLoader.from_youtube_url(
                self.url,
                transcript_format=TranscriptFormat.TEXT
                if self.transcript_format == "text"
                else TranscriptFormat.CHUNKS,
                chunk_size_seconds=self.chunk_size_seconds,
                language=languages,
                translation=self.translation or None,
            )

            transcripts = loader.load()

            if self.transcript_format == "text":
                # Extract only the page_content from the Document
                result = transcripts[0].page_content
                return Message(text=result)

            # For chunks, format the output with timestamps
            formatted_chunks = []
            for doc in transcripts:
                start_seconds = int(doc.metadata["start_seconds"])
                start_minutes = start_seconds // 60
                start_seconds %= 60
                timestamp = f"{start_minutes:02d}:{start_seconds:02d}"
                formatted_chunks.append(f"{timestamp} {doc.page_content}")
                result = "\n".join(formatted_chunks)
            return Message(text=result)

        except Exception as exc:  # noqa: BLE001
            # Using a specific error type for the return value
            error_msg = f"Failed to get YouTube transcripts: {exc!s}"
            return Message(text=error_msg)
