from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import (
    FileInput,
    SecretStrInput,
    MessageTextInput,
    DropdownInput,
    BoolInput,
)
from langflow.template import Output
from langflow.schema.message import Message
from pathlib import Path
from typing import Optional, Any
import requests
import tempfile
import os


class AudioTranscriptionComponent(Component):
    display_name = "Audio Transcription"
    description = "Transcribe audio using various AI models (easily extensible)"
    icon = "microphone"
    name = "AudioTranscription"

    inputs = [
        # Audio Input - File or URL
        FileInput(
            name="audio_file",
            display_name="Audio File",
            file_types=[
                "mp3",
                "wav",
                "m4a",
                "flac",
                "ogg",
                "webm",
                "mp4",
                "mpeg",
                "mpga",
            ],
            info="Upload an audio file",
        ),
        MessageTextInput(
            name="audio_url",
            display_name="Audio URL",
            info="Or provide a URL to an audio file (if file is not uploaded)",
        ),
        # Model Provider Selection
        DropdownInput(
            name="model_provider",
            display_name="Model Provider",
            options=[
                "azure_openai",
                # Add more providers here as you extend
                "openai",
                # "deepgram",
                # "assemblyai",
            ],
            value="azure_openai",
            info="Select the audio transcription provider",
            real_time_refresh=True,
        ),
        # Azure OpenAI Configuration
        SecretStrInput(
            name="azure_api_key",
            display_name="Azure API Key",
            required=True,
        ),
        MessageTextInput(
            name="azure_endpoint",
            display_name="Azure Endpoint",
            placeholder="https://your-resource.openai.azure.com/",
            required=True,
        ),
        MessageTextInput(
            name="azure_deployment_name",
            display_name="Deployment Name",
            placeholder="whisper-deployment",
            required=True,
        ),
        MessageTextInput(
            name="azure_api_version",
            display_name="API Version",
            value="2024-02-01",
        ),
        # Common Transcription Options
        DropdownInput(
            name="language",
            display_name="Language",
            options=[
                "auto",
                "en",
                "es",
                "fr",
                "de",
                "it",
                "pt",
                "nl",
                "ja",
                "ko",
                "zh",
                "ar",
                "ru",
                "hi",
            ],
            value="auto",
            info="Language of the audio (auto for automatic detection)",
        ),
        MessageTextInput(
            name="prompt",
            display_name="Context Prompt",
            info="Optional context to improve accuracy (technical terms, names, etc.)",
            advanced=True,
        ),
        BoolInput(
            name="include_timestamps",
            display_name="Include Timestamps",
            value=False,
            info="Include segment timestamps in output",
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="transcription",
            display_name="Transcription",
            method="transcribe_audio",
        ),
    ]

    def update_build_config(self, build_config, field_value, field_name = None):

        if field_name == "model_provider":
            build_config["azure_endpoint"]["value"] = os.environ.get("OPENAI_WHISPER_API_ENDPOINT", "")
            build_config["azure_api_key"]["value"] = os.environ.get("OPENAI_WHISPER_API_KEY", "")
            build_config["azure_api_version"]["value"] = os.environ.get("OPENAI_WHISPER_API_VERSION", "")
            build_config["azure_deployment_name"]["value"] = os.environ.get("OPENAI_WHISPER_API_DEPLOYMENT_NAME", "whisper")
        
        return build_config

    def transcribe_audio(self) -> Message:
        """Main transcription method - routes to appropriate provider"""
        try:
            # Step 1: Get audio file (from upload or URL)
            audio_file_path = self._get_audio_file()

            if not audio_file_path:
                return Message(text="No audio file or URL provided")

            # Step 2: Route to appropriate provider
            if self.model_provider == "azure_openai":
                result = self._transcribe_azure_openai(audio_file_path)
            # Add more providers here as you extend:
            # elif self.model_provider == "openai":
            #     result = self._transcribe_openai(audio_file_path)
            # elif self.model_provider == "deepgram":
            #     result = self._transcribe_deepgram(audio_file_path)
            else:
                return Message(text=f"Unsupported provider: {self.model_provider}")

            # Step 3: Clean up temporary file if URL was used
            if self.audio_url and not self.audio_file:
                self._cleanup_temp_file(audio_file_path)

            return result

        except Exception as e:
            self.status = f"✗ Error: {str(e)}"
            return Message(
                text=f"Error transcribing audio: {str(e)}", data={"error": str(e)}
            )

    # ==================== AUDIO FILE HANDLING ====================

    def _get_audio_file(self) -> Optional[str]:
        """Get audio file from upload or download from URL"""
        # Priority 1: Uploaded file
        if self.audio_file:
            self.status = f"Using uploaded file: {Path(self.audio_file).name}"
            return self.audio_file

        # Priority 2: URL
        if self.audio_url:
            self.status = f"Downloading audio from URL..."
            return self._download_audio_from_url(self.audio_url)

        return None

    def _download_audio_from_url(self, url: str) -> str:
        """Download audio file from URL to temporary file"""
        try:
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()

            # Determine file extension from URL or Content-Type
            file_extension = self._get_file_extension(url, response)

            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)

            # Download in chunks and track total size
            total_bytes = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filter out keep-alive new chunks
                    temp_file.write(chunk)
                    total_bytes += len(chunk)

            temp_file.close()

            self.status = f"Downloaded audio ({total_bytes:,} bytes)"
            return temp_file.name

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download audio from URL: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to download audio from URL: {str(e)}")

    def _get_file_extension(self, url: str, response: requests.Response) -> str:
        """Determine file extension from URL or Content-Type"""
        # Try to get from URL
        url_path = Path(url.split("?")[0])  # Remove query parameters
        if url_path.suffix:
            return url_path.suffix

        # Try to get from Content-Type
        content_type = response.headers.get("Content-Type", "")
        extension_map = {
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/wav": ".wav",
            "audio/wave": ".wav",
            "audio/x-wav": ".wav",
            "audio/m4a": ".m4a",
            "audio/mp4": ".m4a",
            "audio/flac": ".flac",
            "audio/ogg": ".ogg",
            "audio/webm": ".webm",
        }

        return extension_map.get(content_type, ".mp3")  # Default to .mp3

    def _cleanup_temp_file(self, file_path: str):
        """Clean up temporary file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                self.status = "Cleaned up temporary file"
        except Exception as e:
            # Log but don't fail if cleanup fails
            print(f"Warning: Failed to cleanup temp file: {e}")

    # ==================== PROVIDER IMPLEMENTATIONS ====================

    def _transcribe_azure_openai(self, audio_file_path: str) -> Message:
        """Transcribe using Azure OpenAI Whisper"""
        try:
            from openai import AzureOpenAI
        except ImportError:
            raise ImportError("Install openai: pip install openai")

        # Validate Azure configuration
        self._validate_azure_config()

        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            api_key=self.azure_api_key,
            api_version=self.azure_api_version,
            azure_endpoint=self.azure_endpoint,
        )

        # Prepare transcription parameters
        with open(audio_file_path, "rb") as audio_file:
            params = {
                "model": self.azure_deployment_name,
                "file": audio_file,
            }

            # Add optional parameters
            if self.language and self.language != "auto":
                params["language"] = self.language

            if self.prompt:
                params["prompt"] = self.prompt

            if self.include_timestamps:
                params["response_format"] = "verbose_json"
                params["timestamp_granularities"] = ["segment"]

            # Transcribe
            self.status = "Transcribing with Azure OpenAI..."
            transcript = client.audio.transcriptions.create(**params)

        # Parse response
        transcription_text = self._parse_transcript_response(transcript)

        # Build response data
        data = {
            "transcription": transcription_text,
            "provider": "azure_openai",
            "deployment": self.azure_deployment_name,
            "endpoint": self.azure_endpoint,
            "api_version": self.azure_api_version,
        }

        # Add timestamps if requested
        if self.include_timestamps and hasattr(transcript, "segments"):
            data["segments"] = [
                {
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": seg.get("text"),
                }
                for seg in transcript.segments
            ]

        # Add language if detected
        if hasattr(transcript, "language"):
            data["detected_language"] = transcript.language

        file_name = Path(audio_file_path).name
        self.status = f"✓ Transcribed {file_name}"

        return Message(text=transcription_text, data=data)

    def _validate_azure_config(self):
        """Validate Azure OpenAI configuration"""
        if not self.azure_api_key:
            raise ValueError("Azure API Key is required")

        if not self.azure_endpoint:
            raise ValueError("Azure Endpoint is required")

        if not self.azure_deployment_name:
            raise ValueError("Azure Deployment Name is required")

    def _parse_transcript_response(self, transcript) -> str:
        """Parse transcript response to extract text"""
        if isinstance(transcript, str):
            return transcript
        elif hasattr(transcript, "text"):
            return transcript.text
        else:
            return str(transcript)
