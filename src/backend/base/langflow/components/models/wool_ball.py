import requests
from typing import Any
from langflow.custom import Component
from langflow.io import DropdownInput, Output, StrInput, SecretStrInput, FileInput
from langflow.schema.message import Message
from langflow.schema.dotdict import dotdict
from urllib.parse import unquote
import unicodedata

class WoolBallComponent(Component):
    # Constantes
    API_BASE_URL = "https://api.woolball.xyz"
    TTS_LANGUAGES = ["pt", "en", "es"]
    TASK_TYPES = [
        "Text to Speech",
        "Text Generation",
        "Translation",
        "Zero-Shot Classification",
        "Summary",
        "Character to Image"
    ]

    display_name = "Wool Ball"
    description = "Perform various AI tasks using the Wool Ball API."
    icon = "WoolBall"

    default_keys = ["task_type"]

    def list_languages(self) -> list:
        """List all available languages from the Wool Ball API."""
        try:
            endpoint = "/v1/languages"
            response = requests.get(f"{self.API_BASE_URL}{endpoint}")
            if response.status_code == 200:
                languages_data = response.json().get("data", [])
                # Extrair apenas os códigos dos idiomas
                return [lang["code"] for lang in languages_data]
        except:
            pass
        return ["por_Latn", "eng_Latn", "spa_Latn"]  # Fallback para caso de erro

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
            options=[],  # Será preenchido dinamicamente
            info="The source language for translation.",
        ),
        DropdownInput(
            name="target_language",
            display_name="Target Language",
            options=TTS_LANGUAGES,
            info="The target language for translation or speech.",
        ),
        StrInput(
            name="candidate_labels",
            display_name="Candidate Labels",
            info="Enter possible categories separated by commas (e.g., hungry,travel,question,doubt)",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Your Wool Ball API key.",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="process_task"),
    ]

    def process_task(self) -> Message:
        """Process the selected task using the Wool Ball API."""
        if not self.api_key:
            raise ValueError("API key is required")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            if self.task_type == "Text to Speech":
                return self._handle_tts(headers)

            elif self.task_type == "Text Generation":
                return self._handle_text_generation(headers)

            elif self.task_type == "Translation":
                return self._handle_translation(headers)

            elif self.task_type == "Zero-Shot Classification":
                return self._handle_zero_shot_classification(headers)

            elif self.task_type == "Summary":
                return self._handle_summary(headers)

            elif self.task_type == "Character to Image":
                return self._handle_char_to_image(headers)

            else:
                raise ValueError("Invalid task type selected")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"API request failed: {str(e)}") from e

    def _handle_tts(self, headers):
        """Handle Text to Speech task"""
        if not self.text or not self.target_language:
            raise ValueError("Text and target language are required for Text to Speech")

        endpoint = f"/v1/text-to-speech/{self.target_language}?text={self.text}"
        response = requests.get(f"{self.API_BASE_URL}{endpoint}", headers=headers)
        data = self.handle_api_response(response)
        return Message(text="Audio generated successfully", additional_kwargs={"audio_data": data['data']})

    def _handle_text_generation(self, headers):
        """Handle Text Generation task"""
        if not self.text:
            raise ValueError("Text is required for Text Generation")

        endpoint = f"/v1/completions?text={self.text}"
        response = requests.get(f"{self.API_BASE_URL}{endpoint}", headers=headers)
        data = self.handle_api_response(response)
        return Message(text=data['data'])

    def _handle_translation(self, headers):
        """Handle Translation task"""
        if not self.text or not self.source_language or not self.target_language:
            raise ValueError("Text, source language, and target language are required for Translation")

        endpoint = "/v1/translation"
        payload = {
            "Text": self.text,
            "SrcLang": self.source_language,
            "TgtLang": self.target_language
        }
        response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, json=payload)
        data = self.handle_api_response(response)
        return Message(text=data['data'])

    def _handle_zero_shot_classification(self, headers):
        """Handle Zero-Shot Classification task"""
        if not self.text or not self.candidate_labels:
            raise ValueError("Text and candidate labels are required for Zero-Shot Classification")

        # Limpar e separar as labels, removendo espaços extras
        labels = [label.strip() for label in self.candidate_labels.split(",") if label.strip()]
        
        if not labels:
            raise ValueError("At least one valid candidate label is required")

        endpoint = "/v1/zero-shot-classification"
        payload = {
            "Text": self.text,  # Mudado para "Text" com T maiúsculo
            "CandidateLabels": labels  # Mudado para "CandidateLabels" com C e L maiúsculos
        }

        response = requests.post(
            f"{self.API_BASE_URL}{endpoint}", 
            headers=headers, 
            json=payload
        )
        
        data = self.handle_api_response(response)
        return Message(text=str(data['data']))

    def _handle_summary(self, headers):
        """Handle Summary task"""
        if not self.text:
            raise ValueError("Text is required for Summary")

        endpoint = "/v1/summarization"
        payload = {"text": self.text}
        response = requests.post(f"{self.API_BASE_URL}{endpoint}", headers=headers, json=payload)
        data = self.handle_api_response(response)
        return Message(text=data['data'])

    def _handle_char_to_image(self, headers):
        """Handle Character to Image task"""
        if not self.text:
            raise ValueError("Character is required for Character to Image")

        # Pegar o primeiro caractere visível, mesmo que seja um emoji
        normalized_text = unicodedata.normalize('NFC', self.text.strip())
        # Pegar o primeiro caractere/emoji
        character = next(char for char in normalized_text)
        
        endpoint = "/v1/char-to-image"
        url = f"{self.API_BASE_URL}{endpoint}?character={character}"
        
        response = requests.get(
            url, 
            headers=headers
        )
        
        data = self.handle_api_response(response)
        return Message(
            text="Image generated successfully", 
            additional_kwargs={"image_data": data['data']}
        )

    def handle_api_response(self, response: requests.Response) -> dict:
        """Handle API response and common errors"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise ValueError("Invalid API key.")
            elif e.response.status_code == 429:
                raise ValueError("Rate limit exceeded.")
            raise ValueError(f"HTTP Error: {e.response.status_code}") from e
        except ValueError:
            raise ValueError("Invalid response from API")

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
            fields_to_hide = ["text", "source_language", "target_language", "candidate_labels"]
            for field in fields_to_hide:
                if field in build_config:
                    build_config[field]["show"] = False

            # Atualizar as opções baseado na tarefa
            if field_value == "Text to Speech":
                build_config["target_language"]["options"] = self.TTS_LANGUAGES
            elif field_value == "Translation":
                flowers = self.list_languages()
                build_config["target_language"]["options"] = flowers
                build_config["source_language"]["options"] = flowers

            # Mostrar campos específicos baseado no tipo de tarefa
            field_mapping = {
                "Text to Speech": ["text", "target_language"],
                "Text Generation": ["text"],
                "Translation": ["text", "source_language", "target_language"],
                "Zero-Shot Classification": ["text", "candidate_labels"],
                "Character to Image": ["text"],
                "Summary": ["text"]
            }

            if field_value in field_mapping:
                for field in field_mapping[field_value]:
                    if field in build_config:
                        build_config[field]["show"] = True

        # Garantir que input_types existe em todos os campos
        for key, value in build_config.items():
            if isinstance(value, dict):
                value.setdefault("input_types", [])
            elif hasattr(value, "input_types") and value.input_types is None:
                value.input_types = []

        return build_config