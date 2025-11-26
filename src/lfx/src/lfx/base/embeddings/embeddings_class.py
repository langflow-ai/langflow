"""Extended embeddings class with available models metadata."""

from langchain_core.embeddings import Embeddings


class EmbeddingsWithModels(Embeddings):
    """Extended Embeddings class that includes available models with dedicated instances.

    This class inherits from LangChain Embeddings and provides a mapping of model names
    to their dedicated embedding instances, enabling multi-model support without the need
    for dynamic model switching.

    Attributes:
        embeddings: The primary LangChain Embeddings instance (used as fallback).
        available_models: Dict mapping model names to their dedicated Embeddings instances.
                         Each model has its own pre-configured instance with specific parameters.
    """

    def __init__(
        self,
        embeddings: Embeddings,
        available_models: dict[str, Embeddings] | None = None,
    ):
        """Initialize the EmbeddingsWithModels wrapper.

        Args:
            embeddings: The primary LangChain Embeddings instance (used as default/fallback).
            available_models: Dict mapping model names to dedicated Embeddings instances.
                            Each value should be a fully configured Embeddings object ready to use.
                            Defaults to empty dict if not provided.
        """
        super().__init__()
        self.embeddings = embeddings
        self.available_models = available_models if available_models is not None else {}

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed search docs by delegating to the underlying embeddings instance.

        Args:
            texts: List of text to embed.

        Returns:
            List of embeddings.
        """
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed query text by delegating to the underlying embeddings instance.

        Args:
            text: Text to embed.

        Returns:
            Embedding.
        """
        return self.embeddings.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Asynchronously embed search docs.

        Args:
            texts: List of text to embed.

        Returns:
            List of embeddings.
        """
        return await self.embeddings.aembed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """Asynchronously embed query text.

        Args:
            text: Text to embed.

        Returns:
            Embedding.
        """
        return await self.embeddings.aembed_query(text)

    def __call__(self, *args, **kwargs):
        """Make the class callable by delegating to the underlying embeddings instance.

        This handles cases where the embeddings object is used as a callable.

        Args:
            *args: Positional arguments to pass to the underlying embeddings instance.
            **kwargs: Keyword arguments to pass to the underlying embeddings instance.

        Returns:
            The result of calling the underlying embeddings instance.
        """
        if callable(self.embeddings):
            return self.embeddings(*args, **kwargs)
        msg = f"'{type(self.embeddings).__name__}' object is not callable"
        raise TypeError(msg)

    def __getattr__(self, name: str):
        """Delegate attribute access to the underlying embeddings instance.

        This ensures full compatibility with any additional methods or attributes
        that the underlying embeddings instance might have.

        Args:
            name: The attribute name to access.

        Returns:
            The attribute from the underlying embeddings instance.
        """
        return getattr(self.embeddings, name)

    def __repr__(self) -> str:
        """Return string representation of the wrapper."""
        return f"EmbeddingsWithModels(embeddings={self.embeddings!r}, available_models={self.available_models!r})"
