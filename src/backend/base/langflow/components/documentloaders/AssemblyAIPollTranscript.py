import assemblyai as aai

from langflow.custom import Component
from langflow.io import DataInput, FloatInput, Output, SecretStrInput
from langflow.schema import Data


class AssemblyAITranscriptionJobPoller(Component):
    display_name = "AssemblyAI Poll Transcript"
    description = "Poll for the status of a transcription job using AssemblyAI"
    documentation = "https://www.assemblyai.com/docs"
    icon = "AssemblyAI"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Assembly API Key",
            info="Your AssemblyAI API key. You can get one from https://www.assemblyai.com/",
        ),
        DataInput(
            name="transcript_id",
            display_name="Transcript ID",
            info="The ID of the transcription job to poll",
        ),
        FloatInput(
            name="polling_interval",
            display_name="Polling Interval",
            value=3.0,
            info="The polling interval in seconds",
        ),
    ]

    outputs = [
        Output(display_name="Transcription Result", name="transcription_result", method="poll_transcription_job"),
    ]

    def poll_transcription_job(self) -> Data:
        """Polls the transcription status until completion and returns the Data."""
        aai.settings.api_key = self.api_key
        aai.settings.polling_interval = self.polling_interval

        # check if it's an error message from the previous step
        if self.transcript_id.data.get("error"):
            self.status = self.transcript_id.data["error"]
            return self.transcript_id

        try:
            transcript = aai.Transcript.get_by_id(self.transcript_id.data["transcript_id"])
        except Exception as e:
            error = f"Getting transcription failed: {str(e)}"
            self.status = error
            return Data(data={"error": error})

        if transcript.status == aai.TranscriptStatus.completed:
            data = Data(data=transcript.json_response)
            self.status = data
            return data
        else:
            self.status = transcript.error
            return Data(data={"error": transcript.error})
