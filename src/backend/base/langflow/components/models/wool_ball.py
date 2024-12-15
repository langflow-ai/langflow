import requests
import base64
from typing import Any, Literal
from langflow.custom import Component
from langflow.io import DropdownInput, Output, StrInput, SecretStrInput, FileInput
from langflow.schema.message import Message
from langflow.schema.dotdict import dotdict

class WoolBallComponent(Component):
    # Constantes
    API_BASE_URL = "https://api.woolball.xyz"
    SUPPORTED_LANGUAGES = ["por_Latn", "eng_Latn", "spa_Latn"]
    TASK_TYPES = [
        "Text to Speech",
        "Speech to Text",
        "Text Generation",
        "Translation",
        "Zero-Shot Classification",
        "Facial Emotion Analysis"
    ]

    display_name = "Wool Ball"
    description = "Perform various AI tasks using the Woolball API."
    icon = "WoolBall"

    default_keys = ["task_type", "api_key"]

    inputs = [
        DropdownInput(
            name="task_type",
            display_name="Task Type",
            options=TASK_TYPES,
            info="Select the type of AI processing task.",
            real_time_refresh=True,
        ),
        StrInput(
            name="text",
            display_name="Input Text",
            info="The text to process.",
        ),
        DropdownInput(
            name="source_language",
            display_name="Source Language",
            options=SUPPORTED_LANGUAGES,
            info="The source language for translation.",
        ),
        DropdownInput(
            name="target_language",
            display_name="Target Language",
            options=SUPPORTED_LANGUAGES,
            info="The target language for translation or speech.",
        ),
        StrInput(
            name="candidate_labels",
            display_name="Candidate Labels",
            info="Comma-separated list of candidate labels for zero-shot classification.",
        ),
        FileInput(
            name="file_input",
            display_name="File Input",
            info="The audio file for Speech to Text or image file for Facial Emotion Analysis.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Your Woolball API key.",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="process_task"),
    ]

    def _get_exception_message(self, e: Exception) -> str | None:
        """Get a specific message from API exceptions."""
        if isinstance(e, requests.exceptions.HTTPError):
            if e.response.status_code == 401:
                msg = "Could not validate API key."
                raise ValueError(msg) from e
            elif e.response.status_code == 429:
                msg = "Rate limit exceeded."
                raise ValueError(msg) from e
            msg = f"API request failed: {e.response.status_code}"
            raise ValueError(msg) from e
        return None

    def handle_api_response(self, response: requests.Response) -> dict:
        """Handle API response and common errors"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            self._get_exception_message(e)
        except ValueError as e:
            msg = "Invalid response from API"
            raise ValueError(msg) from e

    def process_task(self) -> Message:
        """Process the selected task using the Woolball API."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            if self.task_type == "Text to Speech":
                endpoint = f"/v1/text-to-speech/{self.target_language}?text={self.text}"
                response = requests.get(f"{self.API_BASE_URL}{endpoint}", headers=headers)
                data = self.handle_api_response(response)
                audio_base64 = data["data"]
                audio_bytes = base64.b64decode(audio_base64)
                audio_size_mb = len(audio_bytes) / (1024 * 1024)
                return Message(
                    text=f"{audio_size_mb:.2f} MB",
                    additional_kwargs={"audio_data": audio_base64}
                )

            elif self.task_type == "Speech to Text":
                if not self.file_input:
                    msg = "Audio file is required for Speech to Text"
                    raise ValueError(msg)
                
                endpoint = "/v1/speech-to-text"
                with open(self.file_input, 'rb') as audio:
                    files = {'audio': audio}
                    response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, files=files)
                data = self.handle_api_response(response)
                return Message(text=data["data"])

            elif self.task_type == "Text Generation":
                endpoint = f"/v1/completions?text={self.text}"
                response = requests.get(f"{self.API_BASE_URL}{endpoint}", headers=headers)
                data = self.handle_api_response(response)
                return Message(text=data["data"])

            elif self.task_type == "Translation":
                endpoint = "/v1/translation"
                payload = {
                    "Text": self.text,
                    "SrcLang": self.source_language,
                    "TgtLang": self.target_language
                }
                response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, json=payload)
                data = self.handle_api_response(response)
                return Message(text=data["data"])

            elif self.task_type == "Zero-Shot Classification":
                endpoint = "/v1/zero-shot-classification"
                candidate_labels = [label.strip() for label in self.candidate_labels.split(',')]
                payload = {
                    "Text": self.text,
                    "CandidateLabels": candidate_labels
                }
                response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, json=payload)
                data = self.handle_api_response(response)
                return Message(text=data["data"])

            elif self.task_type == "Facial Emotion Analysis":
                endpoint = "/v1/image-facial-emotions"
                with open(self.file_input, 'rb') as image:
                    files = {'image': image}
                    response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, files=files)
                data = self.handle_api_response(response)
                return Message(text=data["data"])

            else:
                return Message(text="Please select a task type.")

        except requests.exceptions.RequestException as e:
            msg = f"API request failed: {str(e)}"
            raise ValueError(msg) from e
        except Exception as e:
            raise ValueError(str(e)) from e

    def build(self, *args, **kwargs) -> dotdict:
        """Build the initial configuration for the component."""
        build_config = super().build(*args, **kwargs)
        return self.update_build_config(
            build_config=build_config,
            field_value="Text Generation",
            field_name="task_type"
        )

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "task_type":
            fields_to_hide = ["text", "source_language", "target_language", "candidate_labels", "file_input"]
            for field in fields_to_hide:
                build_config[field]["show"] = False

            field_mapping = {
                "Text to Speech": ["text", "target_language"],
                "Speech to Text": ["file_input"],
                "Text Generation": ["text"],
                "Translation": ["text", "source_language", "target_language"],
                "Zero-Shot Classification": ["text", "candidate_labels"],
                "Facial Emotion Analysis": ["file_input"]
            }

            if field_value in field_mapping:
                for field in field_mapping[field_value]:
                    build_config[field]["show"] = True

        for key, value in build_config.items():
            if isinstance(value, dict):
                value.setdefault("input_types", [])
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []

        return build_config
