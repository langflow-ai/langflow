from typing import Any

import httpx


class AimlModels:
    def __init__(self):
        self.chat_models = []
        self.image_models = []
        self.embedding_models = []
        self.stt_models = []
        self.tts_models = []
        self.language_models = []

    def get_aiml_models(self) -> list[dict[str, Any]]:
        try:
            with httpx.Client() as client:
                response = client.get("https://api.aimlapi.com/models")
                response.raise_for_status()
                models = response.json().get("data", [])
                self.separate_models_by_type(models)
        except httpx.RequestError as e:
            self.get_exception_message(e)
        except httpx.HTTPStatusError as e:
            self.get_exception_message(e)
        except ValueError as e:
            self.get_exception_message(e)

    def separate_models_by_type(self, models):
        model_type_mapping = {
            "chat-completion": self.chat_models,
            "image": self.image_models,
            "embedding": self.embedding_models,
            "stt": self.stt_models,
            "tts": self.tts_models,
            "language-completion": self.language_models,
        }

        for model in models:
            model_type = model.get("type")
            model_id = model.get("id")
            if model_type in model_type_mapping:
                model_type_mapping[model_type].append(model_id)

    def get_exception_message(self, e: Exception):
        return str(e)
