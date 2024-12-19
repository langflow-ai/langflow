"""Compatible api for OpenAI embedding.

inspire: fork by langchain_openai.OpenAIEmbeddings
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Mapping, Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
)

import openai
from langchain_core.embeddings import Embeddings
from langchain_core.utils import from_env, get_pydantic_field_names, secret_from_env
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

if TYPE_CHECKING:
    from typing_extensions import Self

logger = logging.getLogger(__name__)


class OpenAIEmbeddingsCompatible(BaseModel, Embeddings):
    """OpenAI embedding model integration.

    Setup:
        Install ``langchain_openai`` and set environment variable ``OPENAI_API_KEY``.

        .. code-block:: bash

            pip install -U langchain_openai
            export OPENAI_API_KEY="your-api-key"

    Key init args — embedding params:
        model: str
            Name of OpenAI model to use.
        dimensions: Optional[int] = None
            The number of dimensions the resulting output embeddings should have.
            Only supported in `text-embedding-3` and later models.

    Key init args — client params:
        api_key: Optional[SecretStr] = None
            OpenAI API key.
        organization: Optional[str] = None
            OpenAI organization ID. If not passed in will be read
            from env var OPENAI_ORG_ID.
        max_retries: int = 2
            Maximum number of retries to make when generating.
        request_timeout: Optional[Union[float, Tuple[float, float], Any]] = None
            Timeout for requests to OpenAI completion API

    See full list of supported init args and their descriptions in the params section.

    Instantiate:
        .. code-block:: python

            from langchain_openai import OpenAIEmbeddings

            embed = OpenAIEmbeddings(
                model="text-embedding-3-large"
                # With the `text-embedding-3` class
                # of models, you can specify the size
                # of the embeddings you want returned.
                # dimensions=1024
            )

    Embed single text:
        .. code-block:: python

            input_text = "The meaning of life is 42"
            vector = embeddings.embed_query("hello")
            print(vector[:3])

        .. code-block:: python

            [-0.024603435769677162, -0.007543657906353474, 0.0039630369283258915]

    Embed multiple texts:
        .. code-block:: python

            vectors = embeddings.embed_documents(["hello", "goodbye"])
            # Showing only the first 3 coordinates
            print(len(vectors))
            print(vectors[0][:3])

        .. code-block:: python

            2
            [-0.024603435769677162, -0.007543657906353474, 0.0039630369283258915]

    Async:
        .. code-block:: python

            await embed.aembed_query(input_text)
            print(vector[:3])

            # multiple:
            # await embed.aembed_documents(input_texts)

        .. code-block:: python

            [-0.009100092574954033, 0.005071679595857859, -0.0029193938244134188]
    """

    client: Any = Field(default=None, exclude=True)  #: :meta private:
    async_client: Any = Field(default=None, exclude=True)  #: :meta private:
    model: str = "text-embedding-v3"
    dimensions: int | None = None
    """The number of dimensions the resulting output embeddings should have.

    Only supported in `text-embedding-3` and later models.
    """
    # to support Azure OpenAI Service custom deployment names
    deployment: str | None = model
    # to support Azure OpenAI Service custom endpoints
    openai_api_base: str | None = Field(alias="base_url", default_factory=from_env("OPENAI_API_BASE", default=None))
    """Base URL path for API requests, leave blank if not using a proxy or service
        emulator."""
    # to support Azure OpenAI Service custom endpoints
    openai_api_type: str | None = Field(default_factory=from_env("OPENAI_API_TYPE", default=None))
    # to support explicit proxy for OpenAI
    openai_proxy: str | None = Field(default_factory=from_env("OPENAI_PROXY", default=None))
    embedding_ctx_length: int = 8191
    """The maximum number of tokens to embed at once."""
    openai_api_key: SecretStr | None = Field(
        alias="api_key", default_factory=secret_from_env("OPENAI_API_KEY", default=None)
    )
    """Automatically inferred from env var `OPENAI_API_KEY` if not provided."""
    openai_organization: str | None = Field(
        alias="organization",
        default_factory=from_env(["OPENAI_ORG_ID", "OPENAI_ORGANIZATION"], default=None),
    )
    """Automatically inferred from env var `OPENAI_ORG_ID` if not provided."""
    allowed_special: Literal["all"] | set[str] | None = None
    disallowed_special: Literal["all"] | set[str] | Sequence[str] | None = None
    chunk_size: int = 1000
    """Maximum number of texts to embed in each batch"""
    max_retries: int = 2
    """Maximum number of retries to make when generating."""
    request_timeout: float | tuple[float, float] | Any | None = Field(default=None, alias="timeout")
    """Timeout for requests to OpenAI completion API. Can be float, httpx.Timeout or
        None."""
    headers: Any = None
    show_progress_bar: bool = False
    """Whether to show a progress bar when embedding."""
    model_kwargs: dict[str, Any] = Field(default_factory=dict)
    """Holds any model parameters valid for `create` call not explicitly specified."""
    skip_empty: bool = False
    """Whether to skip empty strings when embedding or raise an error.
    Defaults to not skipping."""
    default_headers: Mapping[str, str] | None = None
    default_query: Mapping[str, object] | None = None
    # Configure a custom httpx client. See the
    # [httpx documentation](https://www.python-httpx.org/api/#client) for more details.
    retry_min_seconds: int = 4
    """Min number of seconds to wait between retries"""
    retry_max_seconds: int = 20
    """Max number of seconds to wait between retries"""
    http_client: Any | None = None
    """Optional httpx.Client. Only used for sync invocations. Must specify
        http_async_client as well if you'd like a custom client for async invocations.
    """
    http_async_client: Any | None = None
    """Optional httpx.AsyncClient. Only used for async invocations. Must specify
        http_client as well if you'd like a custom client for sync invocations."""
    # check_embedding_ctx_length: bool = False
    """Whether to check the token length of inputs and automatically split inputs
        longer than embedding_ctx_length."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, protected_namespaces=())

    @model_validator(mode="before")
    @classmethod
    def build_extra(cls, values: dict[str, Any]) -> Any:
        """Build extra kwargs from additional params that were passed in."""
        all_required_field_names = get_pydantic_field_names(cls)
        extra = values.get("model_kwargs", {})
        for field_name in list(values):
            if field_name in extra:
                msg = f"Found {field_name} supplied twice."
                raise ValueError(msg)
            if field_name not in all_required_field_names:
                warnings.warn(  # noqa: B028
                    f"""WARNING! {field_name} is not default parameter.
                    {field_name} was transferred to model_kwargs.
                    Please confirm that {field_name} is what you intended."""
                )
                extra[field_name] = values.pop(field_name)

        invalid_model_kwargs = all_required_field_names.intersection(extra.keys())
        if invalid_model_kwargs:
            msg = (
                f"Parameters {invalid_model_kwargs} should be specified explicitly. "
                f"Instead they were passed in as part of `model_kwargs` parameter."
            )
            raise ValueError(msg)

        values["model_kwargs"] = extra
        return values

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        """Validate that api key and python package exists in environment."""
        if self.openai_api_type in ("azure", "azure_ad", "azuread"):
            msg = "If you are using Azure, " "please use the `AzureOpenAIEmbeddings` class."
            raise ValueError(msg)
        client_params: dict = {
            "api_key": (self.openai_api_key.get_secret_value() if self.openai_api_key else None),
            "organization": self.openai_organization,
            "base_url": self.openai_api_base,
            "timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "default_headers": self.default_headers,
            "default_query": self.default_query,
        }

        if self.openai_proxy and (self.http_client or self.http_async_client):
            openai_proxy = self.openai_proxy
            http_client = self.http_client
            http_async_client = self.http_async_client
            msg = (
                "Cannot specify 'openai_proxy' if one of "
                "'http_client'/'http_async_client' is already specified. Received:\n"
                f"{openai_proxy=}\n{http_client=}\n{http_async_client=}"
            )
            raise ValueError(msg)
        if not self.client:
            if self.openai_proxy and not self.http_client:
                try:
                    import httpx
                except ImportError as e:
                    msg = "Could not import httpx python package. " "Please install it with `pip install httpx`."
                    raise ImportError(msg) from e
                self.http_client = httpx.Client(proxy=self.openai_proxy)
            sync_specific = {"http_client": self.http_client}
            self.client = openai.OpenAI(**client_params, **sync_specific).embeddings  # type: ignore[arg-type]
        if not self.async_client:
            if self.openai_proxy and not self.http_async_client:
                try:
                    import httpx
                except ImportError as e:
                    msg = "Could not import httpx python package. " "Please install it with `pip install httpx`."
                    raise ImportError(msg) from e
                self.http_async_client = httpx.AsyncClient(proxy=self.openai_proxy)
            async_specific = {"http_client": self.http_async_client}
            self.async_client = openai.AsyncOpenAI(
                **client_params,
                **async_specific,  # type: ignore[arg-type]
            ).embeddings
        return self

    @property
    def _invocation_params(self) -> dict[str, Any]:
        params: dict = {"model": self.model, **self.model_kwargs}
        if self.dimensions is not None:
            params["dimensions"] = self.dimensions
        return params

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Call out to OpenAI's embedding endpoint for embedding search docs.

        Args:
            texts: The list of texts to embed.

        Returns:
            List of embeddings, one for each text.
        """
        embeddings: list[list[float]] = []
        for i in range(len(texts)):
            response = self.client.create(input=texts[i], **self._invocation_params)
            if not isinstance(response, dict):
                response = response.dict()
            embeddings.extend(r["embedding"] for r in response["data"])
        return embeddings

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Call out to OpenAI's embedding endpoint async for embedding search docs.

        Args:
            texts: The list of texts to embed.

        Returns:
            List of embeddings, one for each text.
        """
        embeddings: list[list[float]] = []
        for i in range(len(texts)):
            response = await self.async_client.create(input=texts[i], **self._invocation_params)
            if not isinstance(response, dict):
                response = response.dict()
            embeddings.extend(r["embedding"] for r in response["data"])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """Call out to OpenAI's embedding endpoint for embedding query text.

        Args:
            text: The text to embed.

        Returns:
            Embedding for the text.
        """
        return self.embed_documents([text])[0]

    async def aembed_query(self, text: str) -> list[float]:
        """Call out to OpenAI's embedding endpoint async for embedding query text.

        Args:
            text: The text to embed.

        Returns:
            Embedding for the text.
        """
        embeddings = await self.aembed_documents([text])
        return embeddings[0]
