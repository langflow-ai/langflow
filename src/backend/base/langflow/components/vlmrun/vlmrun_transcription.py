import json
from pathlib import Path

from loguru import logger

from langflow.custom.custom_component.component import Component
from langflow.io import (
    DropdownInput,
    FileInput,
    MessageTextInput,
    Output,
    SecretStrInput,
)
from langflow.schema.data import Data


class VLMRunTranscription(Component):
    display_name = "VLM Run Transcription"
    description = "Extract structured data from audio and video using VLM Run AI"
    documentation = "https://docs.vlm.run"
    icon = "VLMRun"
    beta = True

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="VLM Run API Key",
            info="Get your API key from https://app.vlm.run",
            required=True,
        ),
        DropdownInput(
            name="media_type",
            display_name="Media Type",
            options=["audio", "video"],
            value="audio",
            info="Select the type of media to process",
        ),
        FileInput(
            name="media_file",
            display_name="Media File",
            file_types=[
                "mp3", "wav", "m4a", "flac", "ogg", "opus", "webm", "aac",
                "mp4", "mov", "avi", "mkv", "flv", "wmv", "m4v"
            ],
            info="Upload an audio or video file",
            required=False,
        ),
        MessageTextInput(
            name="media_url",
            display_name="Media URL",
            info="URL to media file (alternative to file upload)",
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Result",
            name="result",
            method="process_media",
        ),
    ]

    def process_media(self) -> Data:
        """Process audio or video file and extract structured data."""
        # Validate inputs
        if not self.media_file and not self.media_url:
            error_msg = "Either media file or media URL must be provided"
            self.status = error_msg
            return Data(data={"error": error_msg})

        try:
            # Import VLM Run client
            try:
                from vlmrun.client import VLMRun
            except ImportError:
                error_msg = "VLM Run SDK not installed. Run: pip install 'vlmrun[all]'"
                self.status = error_msg
                return Data(data={"error": error_msg})

            # Initialize client
            client = VLMRun(api_key=self.api_key)
            
            # Process based on media type and source
            if self.media_type == "audio":
                if self.media_file:
                    response = client.audio.generate(
                        file=Path(self.media_file),
                        domain="audio.transcription",
                        batch=True
                    )
                else:
                    response = client.audio.generate(
                        url=self.media_url,
                        domain="audio.transcription",
                        batch=True
                    )
            else:  # video
                if self.media_file:
                    response = client.video.generate(
                        file=Path(self.media_file),
                        domain="video.transcription",
                        batch=True
                    )
                else:
                    response = client.video.generate(
                        url=self.media_url,
                        domain="video.transcription",
                        batch=True
                    )
            
            # Wait for batch processing to complete
            if hasattr(response, 'id'):
                response = client.predictions.wait(id=response.id, timeout=600)
            
            # Extract response data
            response_data = response.response if hasattr(response, 'response') else {}
            
            # Extract transcription from segments
            transcription_parts = []
            segments = response_data.get("segments", [])
            
            for segment in segments:
                if self.media_type == "audio" and "audio" in segment:
                    transcription_parts.append(segment["audio"].get("content", ""))
                elif self.media_type == "video" and "video" in segment:
                    transcription_parts.append(segment["video"].get("content", ""))
                    # Also include audio if available for video
                    if "audio" in segment:
                        audio_content = segment["audio"].get("content", "")
                        if audio_content and audio_content.strip():
                            transcription_parts.append(f"[Audio: {audio_content}]")
            
            # Create output data
            output_data = {
                "transcription": " ".join(transcription_parts),
                "full_response": response_data,
                "metadata": {
                    "media_type": self.media_type,
                    "duration": response_data.get("metadata", {}).get("duration", 0),
                }
            }
            
            self.status = "Processing completed successfully"
            return Data(data=output_data)
            
        except Exception as e:
            logger.opt(exception=True).debug("Error processing media with VLM Run")
            error_msg = f"Processing failed: {str(e)}"
            self.status = error_msg
            return Data(data={"error": error_msg})