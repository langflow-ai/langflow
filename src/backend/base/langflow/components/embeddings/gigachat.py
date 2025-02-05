from langchain_gigachat import GigaChatEmbeddings

from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.base.models.gigachat_constants import GIGACHAT_EMBEDDING_MODEL_NAMES, GIGACHAT_SCOPE_NAMES
from langflow.field_typing import Embeddings
from langflow.io import DropdownInput, SecretStrInput, StrInput


class GigaChatEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "GigaChat Embeddings"
    description = "Generate embeddings using GigaChat models."
    icon = "GigaChat"
    name = "GigaChatEmbeddings"

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=False,
            options=GIGACHAT_EMBEDDING_MODEL_NAMES,
            value=GIGACHAT_EMBEDDING_MODEL_NAMES[0],
        ),
        StrInput(
            name="gigachat_api_base",
            display_name="GigaChat API Base",
            advanced=True,
            info="The base URL of the GigaChat API. ",
        ),
        DropdownInput(
            name="scope",
            display_name="Credentials scope",
            advanced=False,
            options=GIGACHAT_SCOPE_NAMES,
            value=GIGACHAT_SCOPE_NAMES[0],
        ),
        SecretStrInput(
            name="gigachat_credentials",
            display_name="GigaChat credentials",
            info="GigaChat credentials",
            advanced=False,
            value="GIGACHAT_CREDENTIALS",
        ),
        StrInput(
            name="gigachat_user",
            display_name="GigaChat User",
            advanced=True,
            info="GigaChat user",
        ),
        SecretStrInput(
            name="password",
            display_name="GigaChat password",
            info="GigaChat password",
            advanced=True,
            value="GIGACHAT_PASSWORD",
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        return GigaChatEmbeddings(
            model=self.model,
            credentials=self.gigachat_credentials,
            user=self.gigachat_user or None,
            password=self.password or None,
            base_url=self.gigachat_api_base or None,
            scope=self.scope,
            verify_ssl_certs=False,
        )
