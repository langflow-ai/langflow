from pathlib import Path

import assemblyai as aai
from lfx.custom.custom_component.component import Component
from loguru import logger

from langflow.io import BoolInput, DropdownInput, FileInput, MessageTextInput, Output, SecretStrInput
from langflow.schema.data import Data


class AssemblyAITranscriptionJobCreator(Component):
    display_name = "AssemblyAI Start Transcript"
    description = "Create a transcription job for an audio file using AssemblyAI with advanced options"
    documentation = "https://www.assemblyai.com/docs"
    icon = "AssemblyAI"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Assembly API Key",
            info="Your AssemblyAI API key. You can get one from https://www.assemblyai.com/",
            required=True,
        ),
        FileInput(
            name="audio_file",
            display_name="Audio File",
            file_types=[
                "3ga",
                "8svx",
                "aac",
                "ac3",
                "aif",
                "aiff",
                "alac",
                "amr",
                "ape",
                "au",
                "dss",
                "flac",
                "flv",
                "m4a",
                "m4b",
                "m4p",
                "m4r",
                "mp3",
                "mpga",
                "ogg",
                "oga",
                "mogg",
                "opus",
                "qcp",
                "tta",
                "voc",
                "wav",
                "wma",
                "wv",
                "webm",
                "mts",
                "m2ts",
                "ts",
                "mov",
                "mp2",
                "mp4",
                "m4p",
                "m4v",
                "mxf",
            ],
            info="The audio file to transcribe",
            required=True,
        ),
        MessageTextInput(
            name="audio_file_url",
            display_name="Audio File URL",
            info="The URL of the audio file to transcribe (Can be used instead of a File)",
            advanced=True,
        ),
        DropdownInput(
            name="speech_model",
            display_name="Speech Model",
            options=[
                "best",
                "nano",
            ],
            value="best",
            info="The speech model to use for the transcription",
            advanced=True,
        ),
        BoolInput(
            name="language_detection",
            display_name="Automatic Language Detection",
            info="Enable automatic language detection",
            advanced=True,
        ),
        MessageTextInput(
            name="language_code",
            display_name="Language",
            info=(
                """
            The language of the audio file. Can be set manually if automatic language detection is disabled.
            See https://www.assemblyai.com/docs/getting-started/supported-languages """
                "for a list of supported language codes."
            ),
            advanced=True,
        ),
        BoolInput(
            name="speaker_labels",
            display_name="Enable Speaker Labels",
            info="Enable speaker diarization",
        ),
        MessageTextInput(
            name="speakers_expected",
            display_name="Expected Number of Speakers",
            info="Set the expected number of speakers (optional, enter a number)",
            advanced=True,
        ),
        BoolInput(
            name="punctuate",
            display_name="Punctuate",
            info="Enable automatic punctuation",
            advanced=True,
            value=True,
        ),
        BoolInput(
            name="format_text",
            display_name="Format Text",
            info="Enable text formatting",
            advanced=True,
            value=True,
        ),
    ]

    outputs = [
        Output(display_name="Transcript ID", name="transcript_id", method="create_transcription_job"),
    ]

    def create_transcription_job(self) -> Data:
        aai.settings.api_key = self.api_key

        # Convert speakers_expected to int if it's not empty
        speakers_expected = None
        if self.speakers_expected and self.speakers_expected.strip():
            try:
                speakers_expected = int(self.speakers_expected)
            except ValueError:
                self.status = "Error: Expected Number of Speakers must be a valid integer"
                return Data(data={"error": "Error: Expected Number of Speakers must be a valid integer"})

        language_code = self.language_code or None

        config = aai.TranscriptionConfig(
            speech_model=self.speech_model,
            language_detection=self.language_detection,
            language_code=language_code,
            speaker_labels=self.speaker_labels,
            speakers_expected=speakers_expected,
            punctuate=self.punctuate,
            format_text=self.format_text,
        )

        audio = None
        if self.audio_file:
            if self.audio_file_url:
                logger.warning("Both an audio file an audio URL were specified. The audio URL was ignored.")

            # Check if the file exists
            if not Path(self.audio_file).exists():
                self.status = "Error: Audio file not found"
                return Data(data={"error": "Error: Audio file not found"})
            audio = self.audio_file
        elif self.audio_file_url:
            audio = self.audio_file_url
        else:
            self.status = "Error: Either an audio file or an audio URL must be specified"
            return Data(data={"error": "Error: Either an audio file or an audio URL must be specified"})

        try:
            transcript = aai.Transcriber().submit(audio, config=config)
        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error submitting transcription job")
            self.status = f"An error occurred: {e}"
            return Data(data={"error": f"An error occurred: {e}"})

        if transcript.error:
            self.status = transcript.error
            return Data(data={"error": transcript.error})
        result = Data(data={"transcript_id": transcript.id})
        self.status = result
        return result
