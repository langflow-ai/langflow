from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data
from typing import Dict, List
import datetime


class AssemblyAITranscriptionParser(Component):
    display_name = "AssemblyAI Parse Transcript"
    description = "Parse AssemblyAI transcription result. If Speaker Labels was enabled, format utterances with speakers and timestamps"
    documentation = "https://www.assemblyai.com/docs"
    icon = "📊"

    inputs = [
        DataInput(
            name="transcription_result",
            display_name="Transcription Result",
            info="The transcription result from AssemblyAI",
        ),
    ]

    outputs = [
        Output(display_name="Parsed Transcription", name="parsed_transcription", method="parse_transcription"),
    ]

    def parse_transcription(self) -> Data:
        # check if it's an error message from the previous step
        if self.transcription_result.data.get("error"):
            self.status = self.transcription_result.data["error"]
            return self.transcription_result

        try:
            transcription_data = self.transcription_result.data

            if transcription_data.get("utterances"):
                # If speaker diarization was enabled
                parsed_result = self.parse_with_speakers(transcription_data["utterances"])
            elif transcription_data.get("text"):
                # If speaker diarization was not enabled
                parsed_result = transcription_data["text"]
            else:
                raise ValueError("Unexpected transcription format")

            self.status = parsed_result
            return Data(data={"text": parsed_result})
        except Exception as e:
            error_message = f"Error parsing transcription: {str(e)}"
            self.status = error_message
            return Data(data={"error": error_message})

    def parse_with_speakers(self, utterances: List[Dict]) -> str:
        parsed_result = []
        for utterance in utterances:
            speaker = utterance["speaker"]
            start_time = self.format_timestamp(utterance["start"])
            text = utterance["text"]
            parsed_result.append(f'Speaker {speaker} {start_time}\n"{text}"\n')

        return "\n".join(parsed_result)

    def format_timestamp(self, milliseconds: int) -> str:
        return str(datetime.timedelta(milliseconds=milliseconds)).split(".")[0]
