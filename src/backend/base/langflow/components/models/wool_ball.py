import requests
import base64
from typing import Any
from langflow.custom import Component
from langflow.io import DropdownInput, Output, StrInput, SecretStrInput, FileInput, ListInput
from langflow.schema.message import Message
from langflow.schema.dotdict import dotdict

class WoolBallComponent(Component):
    # Constants
    API_BASE_URL = "https://api.woolball.xyz"
    SUPPORTED_LANGUAGES = ["por_Latn", "eng_Latn", "spa_Latn"]
    TASK_TYPES = [
        "Text to Speech",
        "Speech to Text", 
        "Text Generation",
        "Translation",
        "Zero-Shot Classification",
        "Sentiment Analysis",
        "Image+text to text",
        "Image Classification",
        "Zero-Shot Image Classification",
        "Summary and summarization",
        "Character to Image"
    ]

    display_name = "Wool Ball"
    description = "Distributed and Accessible AI Processing powered by Wool Ball"
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
        FileInput(
            name="file_input",
            display_name="File Input",
            info="Audio file for Speech to Text or image file for visual tasks.",
        ),
        ListInput(
            name="candidate_labels",
            display_name="Candidate Labels",
            info="List of candidate labels for classification tasks.",
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

    def _get_exception_message(self, e: Exception) -> str | None:
        """Get a specific message from API exceptions."""
        if isinstance(e, requests.exceptions.HTTPError):
            if e.response.status_code == 401:
                raise ValueError("Could not validate API key.") from e
            elif e.response.status_code == 429:
                raise ValueError("Rate limit exceeded.") from e
            raise ValueError(f"API request failed: {e.response.status_code}") from e
        return None

    def handle_api_response(self, response: requests.Response) -> dict:
        """Handle API response and common errors"""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            self._get_exception_message(e)
        except ValueError as e:
            raise ValueError("Invalid response from API") from e

    def process_task(self) -> Message:
        """Process the selected task using the Wool Ball API."""
        if not self.api_key:
            raise ValueError("API key is required")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            # Map tasks to their respective endpoints and processing logic
            task_handlers = {
                "Text to Speech": self._handle_tts,
                "Speech to Text": self._handle_stt,
                "Text Generation": self._handle_text_generation,
                "Translation": self._handle_translation,
                "Zero-Shot Classification": self._handle_zero_shot,
                "Sentiment Analysis": self._handle_sentiment,
                "Image+text to text": self._handle_image_text,
                "Image Classification": self._handle_image_classification,
                "Zero-Shot Image Classification": self._handle_zero_shot_image,
                "Summary and summarization": self._handle_summary,
                "Character to Image": self._handle_char_to_image
            }

            handler = task_handlers.get(self.task_type)
            if handler:
                return handler(headers)
            return Message(text="Please select a valid task type.")

        except requests.exceptions.RequestException as e:
            raise ValueError(f"API request failed: {str(e)}") from e
        except Exception as e:
            raise ValueError(str(e)) from e

    # Individual task handlers
    def _handle_tts(self, headers):
        """Handle Text to Speech task"""
        if not self.text:
            raise ValueError("Text is required for Text to Speech")
        if not self.target_language:
            raise ValueError("Target language is required for Text to Speech")

        endpoint = f"/v1/text-to-speech/{self.target_language}"
        response = requests.get(
            f"{self.API_BASE_URL}{endpoint}",
            headers=headers,
            params={"text": self.text}
        )
        data = self.handle_api_response(response)
        
        # A API retorna o áudio em base64 diretamente no data
        # Não há uma chave 'audio' no response
        return Message(
            text="Audio generated successfully", 
            additional_kwargs={"audio_data": data}  # Usar data diretamente, sem tentar acessar ['audio']
        )

    def _handle_stt(self, headers):
        """Handle Speech to Text task"""
        if not self.file_input:
            raise ValueError("Audio file is required for Speech to Text")
        
        endpoint = "/v1/speech-to-text"
        with open(self.file_input, 'rb') as audio:
            files = {'audio': audio}
            response = requests.post(
                f"{self.API_BASE_URL}{endpoint}",
                headers=headers,
                files=files
            )
        data = self.handle_api_response(response)
        return Message(text=data["text"])

    def _handle_text_generation(self, headers):
        """Handle Text Generation task"""
        endpoint = "/v1/completions"
        response = requests.post(
            f"{self.API_BASE_URL}{endpoint}",
            headers=headers,
            json={"text": self.text}
        )
        data = self.handle_api_response(response)
        return Message(text=data["generated_text"])

    def _handle_translation(self, headers):
        """Handle Translation task"""
        endpoint = "/v1/translation"
        payload = {
            "text": self.text,
            "source_language": self.source_language,
            "target_language": self.target_language
        }
        response = requests.post(
            f"{self.API_BASE_URL}{endpoint}",
            headers=headers,
            json=payload
        )
        data = self.handle_api_response(response)
        return Message(text=data["translated_text"])

    def _handle_zero_shot(self, headers):
        """Handle Zero-Shot Classification task"""
        if not self.text:
            raise ValueError("Text is required for Zero-Shot Classification")
        if not self.candidate_labels:
            raise ValueError("Candidate labels are required for Zero-Shot Classification")

        endpoint = "/v1/zero-shot-classification"
        
        # Payload com as chaves corretas (primeira letra maiúscula)
        payload = {
            "Text": self.text,
            "CandidateLabels": self.candidate_labels
        }
        
        try:
            response = requests.post(
                f"{self.API_BASE_URL}{endpoint}",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                error_message = response.json().get('message', 'Unknown error')
                raise ValueError(f"API request failed: {response.status_code} - {error_message}")
            
            data = self.handle_api_response(response)
            return Message(text=str(data["classifications"]))
        except requests.exceptions.RequestException as e:
            error_message = getattr(e.response, 'text', str(e))
            raise ValueError(f"API request failed: {error_message}") from e

    def _handle_sentiment(self, headers):
        """Handle Sentiment Analysis task"""
        if not self.file_input:
            raise ValueError("Image file is required for Sentiment Analysis")
        
        endpoint = "/v1/sentiment-analysis"
        with open(self.file_input, 'rb') as image:
            files = {'image': image}
            response = requests.post(
                f"{self.API_BASE_URL}{endpoint}",
                headers=headers,
                files=files
            )
        data = self.handle_api_response(response)
        return Message(text=str(data["sentiment"]))

    def _handle_image_text(self, headers):
        """Handle Image+text to text task"""
        if not self.file_input:
            raise ValueError("Image file is required for Image+text to text")
        if not self.text:
            raise ValueError("Text is required for Image+text to text")
        
        endpoint = "/v1/image-text-to-text"
        
        # Preparar o arquivo de imagem
        with open(self.file_input, 'rb') as image:
            # Criar o payload multipart/form-data
            files = {'image': image}
            data = {'text': self.text}
            
            response = requests.post(
                f"{self.API_BASE_URL}{endpoint}",
                headers=headers,
                files=files,
                data=data  # Usar data em vez de json para multipart/form-data
            )
        
        data = self.handle_api_response(response)
        return Message(text=data["generated_text"])

    def _handle_image_classification(self, headers):
        """Handle Image Classification task"""
        if not self.file_input:
            raise ValueError("Image file is required for Image Classification")
        
        endpoint = "/v1/image-classification"
        with open(self.file_input, 'rb') as image:
            files = {'image': image}
            response = requests.post(
                f"{self.API_BASE_URL}{endpoint}",
                headers=headers,
                files=files
            )
        data = self.handle_api_response(response)
        return Message(text=str(data["classifications"]))

    def _handle_zero_shot_image(self, headers):
        """Handle Zero-Shot Image Classification task"""
        if not self.file_input:
            raise ValueError("Image file is required for Zero-Shot Image Classification")
        if not self.candidate_labels:
            raise ValueError("Candidate labels are required for Zero-Shot Image Classification")
        
        endpoint = "/v1/zero-shot-image-classification"
        
        with open(self.file_input, 'rb') as image:
            files = {'image': image}
            payload = {
                'CandidateLabels': self.candidate_labels
            }
            response = requests.post(
                f"{self.API_BASE_URL}{endpoint}",
                headers=headers,
                files=files,
                data=payload
            )
        data = self.handle_api_response(response)
        return Message(text=str(data["classifications"]))

    def _handle_summary(self, headers):
        """Handle Summary and summarization task"""
        endpoint = "/v1/summarization"
        response = requests.post(
            f"{self.API_BASE_URL}{endpoint}",
            headers=headers,
            json={"text": self.text}
        )
        data = self.handle_api_response(response)
        return Message(text=data["data"])

    def _handle_char_to_image(self, headers):
        """Handle Character to Image task"""
        endpoint = "/v1/character-to-image"
        response = requests.post(
            f"{self.API_BASE_URL}{endpoint}",
            headers=headers,
            json={"text": self.text}
        )
        data = self.handle_api_response(response)
        return Message(text="Image generated successfully", additional_kwargs={"image_data": data["image"]})

    def build(self, *args, **kwargs) -> dotdict:
        """Build the initial configuration for the component."""
        # Obter configuração base da classe pai
        build_config = super().build(*args, **kwargs)
        
        # Garantir que é um dotdict
        if not isinstance(build_config, dotdict):
            build_config = dotdict(build_config or {})
        
        # Inicializar campos
        fields_to_init = ["text", "source_language", "target_language", "candidate_labels", "file_input"]
        for field in fields_to_init:
            if field not in build_config:
                build_config[field] = {"show": False}
        
        # Definir task_type padrão
        if "task_type" not in build_config:
            build_config["task_type"] = {"value": "Text Generation"}
        
        # Atualizar visibilidade dos campos
        return self.update_build_config(
            build_config=build_config,
            field_value=build_config["task_type"]["value"],
            field_name="task_type"
        )

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the build configuration based on the selected task."""
        if field_name == "task_type":
            # Garanta que build_config é um dotdict
            if build_config is None:
                build_config = dotdict()
            
            # Inicialize os campos se necessário
            fields_to_hide = ["text", "source_language", "target_language", "candidate_labels", "file_input"]
            for field in fields_to_hide:
                if field not in build_config:
                    build_config[field] = {"show": False}
                build_config[field]["show"] = False

            # Mostre os campos relevantes com base no tipo de tarefa
            field_mapping = {
                "Text to Speech": ["text", "target_language"],
                "Speech to Text": ["file_input"],
                "Text Generation": ["text"],
                "Translation": ["text", "source_language", "target_language"],
                "Zero-Shot Classification": ["text", "candidate_labels"],
                "Sentiment Analysis": ["file_input"],
                "Image+text to text": ["text", "file_input"],
                "Image Classification": ["file_input"],
                "Zero-Shot Image Classification": ["file_input", "candidate_labels"],
                "Summary and summarization": ["text"],
                "Character to Image": ["text"]
            }

            if field_value in field_mapping:
                for field in field_mapping[field_value]:
                    if field in build_config:
                        build_config[field]["show"] = True

        return build_config
