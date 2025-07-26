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
    description = "Extract structured data from audio and video using [VLM Run AI](https://app.vlm.run)"
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
            name="media_files",
            display_name="Media Files",
            file_types=[
                "mp3",
                "wav",
                "m4a",
                "flac",
                "ogg",
                "opus",
                "webm",
                "aac",
                "mp4",
                "mov",
                "avi",
                "mkv",
                "flv",
                "wmv",
                "m4v",
            ],
            info="Upload one or more audio/video files",
            required=False,
            is_list=True,
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
        if not self.media_files and not self.media_url:
            error_msg = "Either media files or media URL must be provided"
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

            # Process files
            all_results = []

            # Handle multiple files
            if self.media_files:
                # Convert to list if single file
                files_to_process = self.media_files if isinstance(self.media_files, list) else [self.media_files]

                for idx, media_file in enumerate(files_to_process):
                    self.status = f"Processing file {idx + 1} of {len(files_to_process)}..."

                    # Process based on media type
                    if self.media_type == "audio":
                        response = client.audio.generate(
                            file=Path(media_file), domain="audio.transcription", batch=True
                        )
                    else:  # video
                        response = client.video.generate(
                            file=Path(media_file), domain="video.transcription", batch=True
                        )

                    # Wait for batch processing to complete
                    if hasattr(response, "id"):
                        response = client.predictions.wait(response.id, timeout=600)

                    # Extract response data
                    response_data = response.response if hasattr(response, "response") else {}

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

                    # Store result for this file
                    file_result = {
                        "filename": Path(media_file).name,
                        "prediction_id": response.id if hasattr(response, "id") else None,
                        "transcription": " ".join(transcription_parts),
                        "full_response": response_data,
                        "metadata": {
                            "media_type": self.media_type,
                            "duration": response_data.get("metadata", {}).get("duration", 0),
                        },
                        "usage": response.usage.__dict__ if hasattr(response, "usage") else None,
                        "status": response.status if hasattr(response, "status") else "completed",
                    }
                    all_results.append(file_result)

            # Handle URL (single processing)
            elif self.media_url:
                if self.media_type == "audio":
                    response = client.audio.generate(url=self.media_url, domain="audio.transcription", batch=True)
                else:  # video
                    response = client.video.generate(url=self.media_url, domain="video.transcription", batch=True)

                # Wait for batch processing to complete
                if hasattr(response, "id"):
                    response = client.predictions.wait(response.id, timeout=600)

                # Extract response data
                response_data = response.response if hasattr(response, "response") else {}

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

                # Store result for URL
                url_result = {
                    "source": self.media_url,
                    "prediction_id": response.id if hasattr(response, "id") else None,
                    "transcription": " ".join(transcription_parts),
                    "full_response": response_data,
                    "metadata": {
                        "media_type": self.media_type,
                        "duration": response_data.get("metadata", {}).get("duration", 0),
                    },
                    "usage": response.usage.__dict__ if hasattr(response, "usage") else None,
                    "status": response.status if hasattr(response, "status") else "completed",
                }
                all_results.append(url_result)

            # Create output data
            if len(all_results) == 1:
                # Single file/URL - return simple format for backward compatibility
                output_data = all_results[0]
            else:
                # Multiple files - return list of results
                output_data = {
                    "results": all_results,
                    "total_files": len(all_results),
                    "combined_transcription": "\n\n---\n\n".join(
                        [
                            f"[{r.get('filename', r.get('source', 'Unknown'))}]\n{r['transcription']}"
                            for r in all_results
                        ]
                    ),
                }

            self.status = f"Successfully processed {len(all_results)} file(s)"
            return Data(data=output_data)

        except (ImportError, ValueError, ConnectionError, TimeoutError) as e:
            logger.opt(exception=True).debug("Error processing media with VLM Run")
            error_msg = f"Processing failed: {e!s}"
            self.status = error_msg
            return Data(data={"error": error_msg})
        except (AttributeError, KeyError, OSError) as e:
            logger.opt(exception=True).debug("Unexpected error processing media with VLM Run")
            error_msg = f"Unexpected error: {e!s}"
            self.status = error_msg
            return Data(data={"error": error_msg})
