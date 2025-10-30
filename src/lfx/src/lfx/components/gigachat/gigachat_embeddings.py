from typing import Any

from gigachat.settings import AUTH_URL, BASE_URL, SCOPE
from langchain_gigachat import GigaChatEmbeddings

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.gigachat_constants import GIGACHAT_EMBEDDING_MODEL_NAMES
from lfx.field_typing import Embeddings
from lfx.io import BoolInput, DropdownInput, IntInput, SecretStrInput, StrInput


class GigaChatEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "GigaChat Embeddings"
    description = "Generate embeddings using GigaChat models."
    name = "GigaChatEmbeddings"
    icon = "GigaChat"

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model Name",
            advanced=False,
            options=GIGACHAT_EMBEDDING_MODEL_NAMES,
            value=GIGACHAT_EMBEDDING_MODEL_NAMES[0],
        ),
        StrInput(
            name="base_url",
            display_name="GigaChat API Base",
            advanced=True,
            value=BASE_URL,
            info=f"The base URL of the GigaChat API. Defaults to {BASE_URL}. ",
        ),
        StrInput(
            name="auth_url",
            display_name="GigaChat Auth URL",
            advanced=True,
            value=AUTH_URL,
            info=f"The auth URL of the GigaChat API. Defaults to {AUTH_URL}. ",
        ),
        StrInput(
            name="scope",
            display_name="GigaChat Scope",
            advanced=False,
            value=SCOPE,
            info=f"The scope of the GigaChat API. Defaults to {SCOPE}. ",
        ),
        SecretStrInput(
            name="credentials",
            display_name="GigaChat Credentials",
            info="The GigaChat API Key to use for the GigaChat model.",
            advanced=False,
            value=None,
            required=False,
        ),
        StrInput(
            name="user",
            display_name="GigaChat User",
            info="The GigaChat API Username to use.",
            advanced=True,
            value="USERNAME",
            required=False,
        ),
        SecretStrInput(
            name="password",
            display_name="GigaChat Password",
            info="The GigaChat API Password to use.",
            advanced=True,
            value=None,
            required=False,
        ),
        BoolInput(
            name="verify_ssl_certs",
            display_name="verify_ssl_certs",
            value=False,
            advanced=True,
            info="Проверка SSL сертов",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="The timeout for requests to GigaChat API.",
            advanced=True,
            value=700,
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        parameters: dict[str, Any] = {
            "base_url": self.base_url,
            "auth_url": self.auth_url,
            "credentials": self.credentials,
            "scope": self.scope,
            "model": self.model,
            "user": self.user,
            "password": self.password,
            "timeout": self.timeout,
            "verify_ssl_certs": self.verify_ssl_certs,
        }
        return GigaChatEmbeddings(**parameters)
