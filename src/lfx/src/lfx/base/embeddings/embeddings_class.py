"""Extended embeddings class with available models metadata."""

from langchain_core.embeddings import Embeddings


class EmbeddingsWithModels(Embeddings):
    """Extended Embeddings class that includes available models metadata.

    This class inherits from LangChain Embeddings and adds an available_models
    field to store the list of available model providers/names.

    Attributes:
        embeddings: The underlying LangChain Embeddings instance.
        available_models: List of available model provider names or model identifiers.
    """

    def __init__(self, embeddings: Embeddings, available_models: list[str] | None = None):
        """Initialize the EmbeddingsWithModels wrapper.

        Args:
            embeddings: The LangChain Embeddings instance to wrap.
            available_models: Optional list of available model names. Defaults to empty list.
        """
        super().__init__()
        self.embeddings = embeddings
        self.available_models = available_models or []

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
        return (
            f"EmbeddingsWithModels(embeddings={self.embeddings!r}, "
            f"available_models={self.available_models!r})"
        )

