import logging
import requests
import unicodedata
from typing import Any

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, Output, SecretStrInput
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message

# Define constants for status codes
SUCCESS_STATUS_CODE = 200
UNAUTHORIZED_STATUS_CODE = 401
RATE_LIMIT_STATUS_CODE = 429

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WoolBallComponent(Component):
    API_BASE_URL = "https://api.woolball.xyz"
    TTS_LANGUAGES = ["pt", "en", "es"]
    TASK_TYPES = [
        "Text Generation",
        "Text to Speech",
        "Translation",
        "Zero-Shot Classification",
        "Summary",
        "Character to Image",
    ]
    display_name = "Wool Ball"
    description = "Perform various AI tasks using the Wool Ball API."
    icon = "WoolBall"

    default_keys = ["task_type"]

    def list_languages(self) -> list:
        try:
            endpoint = "/v1/languages"
            response = requests.get(f"{self.API_BASE_URL}{endpoint}", timeout=5)
            if response.status_code == SUCCESS_STATUS_CODE:
                languages_data = response.json().get("data", [])
                return [lang["code"] for lang in languages_data]
        except requests.exceptions.RequestException:
            logger.exception("An error occurred while listing languages.")
        return ["por_Latn", "eng_Latn", "spa_Latn"]

    inputs = [
        DropdownInput(
            name="task_type",
            display_name="Task Type",
            options=TASK_TYPES,
            info="Select the type of AI processing task.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="text",
            display_name="Input Text",
            info="The text to process.",
            input_types=["Message"],
            show=False,
        ),
        DropdownInput(
            name="source_language",
            display_name="Source Language",
            options=[],
            info="The source language for translation.",
            input_types=["Message"],
            show=False,
        ),
        DropdownInput(
            name="target_language",
            display_name="Target Language",
            options=TTS_LANGUAGES,
            info="The target language for translation or speech.",
            input_types=["Message"],
            show=False,
        ),
        MessageTextInput(
            name="candidate_labels",
            display_name="Candidate Labels",
            info="Enter possible categories separated by commas",
            input_types=["Message"],
            show=False,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Your Wool Ball API key.",
            input_types=["Message"],
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="process_task"),
    ]

    FIELD_MAPPING = {
        "Text Generation": ["text", "api_key"],
        "Text to Speech": ["text", "target_language", "api_key"],
        "Translation": ["text", "source_language", "target_language", "api_key"],
        "Zero-Shot Classification": ["text", "candidate_labels", "api_key"],
        "Summary": ["text", "api_key"],
        "Character to Image": ["text", "api_key"],
    }

    def build(self, build_config: dotdict) -> dotdict:
        fields_to_hide = ["text", "source_language", "target_language", "candidate_labels"]
        for field in fields_to_hide:
            if field in build_config:
                build_config[field]["show"] = False

        default_task = self.TASK_TYPES[0]
        if default_task in self.FIELD_MAPPING:
            for field in self.FIELD_MAPPING[default_task]:
                if field in build_config:
                    build_config[field]["show"] = True

        return build_config

    def process_task(self) -> Message:
        if not self.api_key:
            error_message = "API key is required"
            raise ValueError(error_message)

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            if self.task_type == "Text to Speech":
                return self._handle_tts(headers)
            if self.task_type == "Text Generation":
                return self._handle_text_generation(headers)
            if self.task_type == "Translation":
                return self._handle_translation(headers)
            if self.task_type == "Zero-Shot Classification":
                return self._handle_zero_shot_classification(headers)
            if self.task_type == "Summary":
                return self._handle_summary(headers)
            if self.task_type == "Character to Image":
                return self._handle_char_to_image(headers)

            error_message = "Invalid task type selected"
            raise ValueError(error_message)
        except requests.exceptions.RequestException as e:
            error_message = "API request failed"
            logger.exception(error_message)
            raise ValueError(error_message) from e

    def _handle_tts(self, headers):
        if not self.text or not self.target_language:
            error_msg = "Text and target language are required for Text to Speech"
            raise ValueError(error_msg)

        endpoint = f"/v1/text-to-speech/{self.target_language}?text={self.text}"
        response = requests.get(f"{self.API_BASE_URL}{endpoint}", headers=headers, timeout=60)
        data = self.handle_api_response(response)
        return Message(text="Audio generated successfully", additional_kwargs={"audio_data": data["data"]})

    def _handle_text_generation(self, headers):
        if not self.text:
            error_message = "Text is required for Text Generation"
            raise ValueError(error_message)

        endpoint = f"/v1/completions?text={self.text}"
        response = requests.get(f"{self.API_BASE_URL}{endpoint}", headers=headers, timeout=60)
        data = self.handle_api_response(response)
        return Message(text=data["data"])

    def _handle_translation(self, headers):
        if not self.text or not self.source_language or not self.target_language:
            error_message = "Text, source language, and target language are required for Translation"
            raise ValueError(error_message)

        endpoint = "/v1/translation"
        payload = {"Text": self.text, "SrcLang": self.source_language, "TgtLang": self.target_language}
        response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, json=payload, timeout=60)
        data = self.handle_api_response(response)
        return Message(text=data["data"])

    def _handle_zero_shot_classification(self, headers):
        if not self.text or not self.candidate_labels:
            error_message = "Text and candidate labels are required for Zero-Shot Classification"
            raise ValueError(error_message)

        labels = [label.strip() for label in self.candidate_labels.split(",") if label.strip()]

        if not labels:
            error_message = "At least one valid candidate label is required for Zero-Shot Classification"
            raise ValueError(error_message)

        endpoint = "/v1/zero-shot-classification"
        payload = {"Text": self.text, "CandidateLabels": labels}

        response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, json=payload, timeout=60)

        data = self.handle_api_response(response)
        return Message(text=str(data["data"]))

    def _handle_summary(self, headers):
        if not self.text:
            error_message = "Text is required for Summary"
            raise ValueError(error_message)

        endpoint = "/v1/summarization"
        payload = {"text": self.text}
        response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, json=payload, timeout=60)
        data = self.handle_api_response(response)
        return Message(text=data["data"])

    def _handle_char_to_image(self, headers):
        if not self.text:
            error_message = "Character is required for Character to Image"
            raise ValueError(error_message)

        normalized_text = unicodedata.normalize("NFC", self.text.strip())
        character = next(char for char in normalized_text)

        endpoint = "/v1/char-to-image"
        url = f"{self.API_BASE_URL}{endpoint}?character={character}"

        response = requests.get(url, headers=headers, timeout=60)

        data = self.handle_api_response(response)
        return Message(text="Image generated successfully", additional_kwargs={"image_data": data["data"]})

    def handle_api_response(self, response: requests.Response) -> dict:
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == UNAUTHORIZED_STATUS_CODE:
                error_message = "Invalid API key."
                raise ValueError(error_message) from None
            if e.response.status_code == RATE_LIMIT_STATUS_CODE:
                error_message = "Rate limit exceeded."
                raise ValueError(error_message) from None
            error_message = f"HTTP Error: {e.response.status_code}"
            raise ValueError(error_message) from e
        except ValueError:
            error_message = "Invalid response from API"
            raise ValueError(error_message) from None

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "task_type":
            fields_to_hide = ["text", "source_language", "target_language", "candidate_labels"]
            for field in fields_to_hide:
                if field in build_config:
                    build_config[field]["show"] = False

            if field_value == "Text to Speech":
                build_config["target_language"]["options"] = self.TTS_LANGUAGES
            elif field_value == "Translation":
                languages = self.list_languages()
                build_config["target_language"]["options"] = languages
                build_config["source_language"]["options"] = languages

            if field_value in self.FIELD_MAPPING:
                for field in self.FIELD_MAPPING[field_value]:
                    if field in build_config:
                        build_config[field]["show"] = True

        return build_config
