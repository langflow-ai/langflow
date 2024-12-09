from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.base.embeddings.openai_embeddings_compatible import (
    OpenAIEmbeddingsCompatible,
)
from langflow.base.models.tongyi_constants import TONGYI_EMBEDDING_MODEL_NAMES
from langflow.field_typing import Embeddings
from langflow.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    SecretStrInput,
)


class TongyiEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "Tongyi Embeddings"
    description = "Generate embeddings using Tongyi models."
    icon = "Tongyi"
    name = "TongyiEmbeddings"

    inputs = [
        DictInput(
            name="default_headers",
            display_name="Default Headers",
            advanced=True,
            info="Default headers to use for the API request.",
        ),
        DictInput(
            name="default_query",
            display_name="Default Query",
            advanced=True,
            info="Default query parameters to use for the API request.",
        ),
        IntInput(name="chunk_size", display_name="Chunk Size", advanced=True, value=6),
        MessageTextInput(name="client", display_name="Client", advanced=True),
        MessageTextInput(name="deployment", display_name="Deployment", advanced=True),
        IntInput(
            name="embedding_ctx_length",
            display_name="Embedding Context Length",
            advanced=True,
            value=1536,
        ),
        IntInput(name="max_retries", display_name="Max Retries", value=3, advanced=True),
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=False,
            options=TONGYI_EMBEDDING_MODEL_NAMES,
            value="text-embedding-v3",
        ),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        SecretStrInput(name="tongyi_api_key", display_name="Tongyi API Key", value="TONGYI_API_KEY"),
        MessageTextInput(
            name="tongyi_api_base",
            display_name="Tongyi API Base",
            advanced=True,
            value="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        MessageTextInput(name="tongyi_api_type", display_name="Tongyi API Type", advanced=True),
        MessageTextInput(
            name="tongyi_organization",
            display_name="Tongyi Organization",
            advanced=True,
        ),
        MessageTextInput(name="tongyi_proxy", display_name="Tongyi Proxy", advanced=True),
        FloatInput(name="request_timeout", display_name="Request Timeout", advanced=True),
        BoolInput(name="show_progress_bar", display_name="Show Progress Bar", advanced=True),
        BoolInput(name="skip_empty", display_name="Skip Empty", advanced=True),
        MessageTextInput(
            name="tiktoken_model_name",
            display_name="TikToken Model Name",
            advanced=True,
        ),
        BoolInput(
            name="tiktoken_enable",
            display_name="TikToken Enable",
            advanced=True,
            value=True,
            info="If False, you must have transformers installed.",
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have. "
            "Only supported by certain models. Only applicable to the text-embedding-v3 model."
            "the user-specified value can only be one of 1024, 768, or 512, with a default value of 1024.",
            advanced=True,
            # value=1024,
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        return OpenAIEmbeddingsCompatible(
            client=self.client or None,
            model=self.model,
            dimensions=self.dimensions or None,
            deployment=self.deployment or None,
            base_url=self.tongyi_api_base or None,
            openai_api_type=self.tongyi_api_type or None,
            openai_proxy=self.tongyi_proxy or None,
            embedding_ctx_length=self.embedding_ctx_length,
            api_key=self.tongyi_api_key or None,
            organization=self.tongyi_organization or None,
            allowed_special="all",
            disallowed_special="all",
            chunk_size=self.chunk_size,
            max_retries=self.max_retries,
            timeout=self.request_timeout or None,
            show_progress_bar=self.show_progress_bar,
            model_kwargs=self.model_kwargs,
            skip_empty=self.skip_empty,
            default_headers=self.default_headers or None,
            default_query=self.default_query or None,
        )
