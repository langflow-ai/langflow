from typing import Any

from langchain_gigachat import GigaChatEmbeddings

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.gigachat_constants import GIGACHAT_EMBEDDING_MODEL_NAMES, GIGACHAT_SCOPES
from lfx.field_typing import Embeddings
from lfx.io import BoolInput, DropdownInput, IntInput, SecretStrInput, StrInput


class GigaChatEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "GigaChat Embeddings"
    description = "Generate embeddings using GigaChat models."
    icon = "GigaChat"

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model Name",
            advanced=False,
            options=GIGACHAT_EMBEDDING_MODEL_NAMES,
            value=GIGACHAT_EMBEDDING_MODEL_NAMES[0],
            real_time_refresh=True,
            combobox=True,
        ),
        StrInput(
            name="base_url",
            display_name="GigaChat API Base",
            advanced=True,
            info="The base URL of the GigaChat API. ",
            value=None,
        ),
        StrInput(
            name="auth_url",
            display_name="GigaChat Auth URL",
            advanced=True,
            info="The auth URL of the GigaChat API. ",
            value=None,
        ),
        DropdownInput(
            name="scope",
            display_name="GigaChat Scope",
            advanced=False,
            options=GIGACHAT_SCOPES,
            real_time_refresh=True,
            value=GIGACHAT_SCOPES[0],
            info="Version of the API you are getting access to. "
            "You can find the value of the scope field in your profile after you create a project.",
            combobox=True,
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
            info="The GigaChat API Username to use (if required by your authentication method).",
            advanced=True,
            value=None,
            required=False,
        ),
        SecretStrInput(
            name="password",
            display_name="GigaChat Password",
            info="The GigaChat API Password to use (if required by your authentication method).",
            advanced=True,
            value=None,
            required=False,
        ),
        BoolInput(
            name="verify_ssl_certs",
            display_name="verify_ssl_certs",
            value=False,
            advanced=True,
            info="Check certificates for all requests",
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
