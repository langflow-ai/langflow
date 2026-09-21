import httpx
from langchain_mistralai import MistralAIEmbeddings
from lfx.base.models.model import LCModelComponent
from lfx.base.models.provider_ssrf import provider_httpx_client_kwargs
from lfx.field_typing import Embeddings
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput
from pydantic.v1 import SecretStr

DEFAULT_MISTRAL_ENDPOINT = "https://api.mistral.ai/v1"


class MistralAIEmbeddingsComponent(LCModelComponent):
    display_name = "MistralAI Embeddings"
    description = "Generate embeddings using MistralAI models."
    icon = "MistralAI"
    name = "MistalAIEmbeddings"

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=False,
            options=["mistral-embed"],
            value="mistral-embed",
        ),
        SecretStrInput(name="mistral_api_key", display_name="Mistral API Key", required=True),
        IntInput(
            name="max_concurrent_requests",
            display_name="Max Concurrent Requests",
            advanced=True,
            value=64,
        ),
        IntInput(name="max_retries", display_name="Max Retries", advanced=True, value=5),
        IntInput(name="timeout", display_name="Request Timeout", advanced=True, value=120),
        MessageTextInput(
            name="endpoint",
            display_name="API Endpoint",
            advanced=True,
            value="https://api.mistral.ai/v1/",
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        if not self.mistral_api_key:
            msg = "Mistral API Key is required"
            raise ValueError(msg)

        api_key = SecretStr(self.mistral_api_key).get_secret_value()

        # endpoint is tenant-editable and the SDK sends the operator's API key to whatever
        # host it names. Route a custom endpoint through DNS-pinned, redirect-free clients
        # (no-op for the default Mistral endpoint).
        #
        # MistralAIEmbeddings only configures its clients inside "if not self.client:", so an
        # injected client has to arrive fully formed: it posts to the *relative* path
        # "/embeddings", and it puts the API key in an Authorization header rather than on
        # the request. A transport-only client therefore has no base URL (httpx raises
        # UnsupportedProtocol on the relative path) and no credentials. Build the clients
        # here to the SDK's contract and keep the pinned transport.
        sync_kwargs, async_kwargs = provider_httpx_client_kwargs(self.endpoint, default_url=DEFAULT_MISTRAL_ENDPOINT)
        client_kwargs = {}
        if sync_kwargs or async_kwargs:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            client_kwargs["client"] = httpx.Client(
                base_url=self.endpoint, headers=headers, timeout=self.timeout, **sync_kwargs
            )
            client_kwargs["async_client"] = httpx.AsyncClient(
                base_url=self.endpoint, headers=headers, timeout=self.timeout, **async_kwargs
            )

        return MistralAIEmbeddings(
            api_key=api_key,
            model=self.model,
            endpoint=self.endpoint,
            max_concurrent_requests=self.max_concurrent_requests,
            max_retries=self.max_retries,
            timeout=self.timeout,
            **client_kwargs,
        )
