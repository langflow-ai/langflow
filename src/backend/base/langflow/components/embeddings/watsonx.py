from langflow.base.models.model import LCModelComponent
from langflow.io import (
    IntInput,
    StrInput,
    SecretStrInput,
    BoolInput,
    DropdownInput,
    Output,
)
from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames
from ibm_watsonx_ai.foundation_models import Embeddings
from ibm_watsonx_ai import APIClient
from ibm_watsonx_ai.credentials import Credentials


class IBMEmbeddingsComponent(LCModelComponent):
    display_name = "IBM Embeddings"
    description = "Generate embeddings using IBM models."
    # icon = "IBM"
    icon = "brain"
    name = "IBMEmbeddingsComponent"

    inputs = [
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=[
                "GRANITE_EMBEDDING_107M_MULTILINGUAL",
                "GRANITE_EMBEDDING_278M_MULTILINGUAL",
                "SLATE_125M_ENGLISH_RTRVR",
                "SLATE_125M_ENGLISH_RTRVR_V2",
                "SLATE_30M_ENGLISH_RTRVR",
                "SLATE_30M_ENGLISH_RTRVR_V2",
            ],
            value="GRANITE_EMBEDDING_107M_MULTILINGUAL",
        ),
        StrInput(
            name="url",
            display_name="IBM watsonx URL",
            value="https://us-south.ml.cloud.ibm.com",
            advanced=True,
        ),
        SecretStrInput(name="api_key", display_name="IBM watsonx API Key"),
        StrInput(
            name="project_id",
            display_name="ID of the Watson Studio project",
        ),
        IntInput(
            name="truncate_input_tokens",
            display_name="The maximum number of tokens to consider from the input text",
            value=512,
            advanced=True,
        ),
        BoolInput(
            name="input_text",
            display_name="Include the original text in the output",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        credentials = Credentials(url=self.url, api_key=self.api_key)
        api_client = APIClient(credentials)

        return Embeddings(
            model_id=api_client.foundation_models.EmbeddingModels[self.model_name],
            params={
                EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS: self.truncate_input_tokens,
                EmbedTextParamsMetaNames.RETURN_OPTIONS: {
                    "input_text": self.input_text
                },
            },
            api_client=api_client,
            project_id=self.project_id,
        )
