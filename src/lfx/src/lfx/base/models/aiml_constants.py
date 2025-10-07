import httpx
from openai import APIConnectionError, APIError


class AimlModels:
    def __init__(self):
        self.chat_models = []
        self.image_models = []
        self.embedding_models = []
        self.stt_models = []
        self.tts_models = []
        self.language_models = []

    def get_aiml_models(self):
        try:
            with httpx.Client() as client:
                response = client.get("https://api.aimlapi.com/models")
                response.raise_for_status()
        except httpx.RequestError as e:
            msg = "Failed to connect to the AI/ML API."
            raise APIConnectionError(msg) from e
        except httpx.HTTPStatusError as e:
            msg = f"AI/ML API responded with status code: {e.response.status_code}"
            raise APIError(
                message=msg,
                body=None,
                request=e.request,
            ) from e

        try:
            models = response.json().get("data", [])
            self.separate_models_by_type(models)
        except (ValueError, KeyError, TypeError) as e:
            msg = "Failed to parse response data from AI/ML API. The format may be incorrect."
            raise ValueError(msg) from e

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
