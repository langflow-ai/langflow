from langchain_sambanova import SambaNovaCloudEmbeddings
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.base.models.sambanova_constants import SAMBANOVA_EMBEDDING_MODEL_NAMES
from langflow.field_typing import Embeddings
from langflow.io import DropdownInput, Output, SecretStrInput

HTTP_STATUS_OK = 200


class SambaNovaEmbeddingsComponent(LCModelComponent):
    display_name = "SambaNova Embeddings"
    description = "Generate embeddings using SambaNova models."
    icon = "SambaNova"
    name = "SambaNovaEmbeddings"

    inputs = [
        SecretStrInput(name="api_key", display_name="SambaNova API Key", required=True, real_time_refresh=True),
        DropdownInput(
            name="model_name",
            display_name="Model",
            advanced=False,
            options=SAMBANOVA_EMBEDDING_MODEL_NAMES,
            value=SAMBANOVA_EMBEDDING_MODEL_NAMES[0] if SAMBANOVA_EMBEDDING_MODEL_NAMES else "",
            refresh_button=True,
            combobox=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        embeddings = None
        api_key = SecretStr(self.api_key).get_secret_value()
        try:
            embeddings = SambaNovaCloudEmbeddings(
                sambanova_api_key=api_key,
                model=self.model_name,
            )
        except Exception as e:
            msg = (
                "Unable to create SambaNova Embeddings. Please verify the API key and model parameters, and try again."
            )
            raise ValueError(msg) from e
        return embeddings
