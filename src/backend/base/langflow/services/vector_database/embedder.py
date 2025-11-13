import logging

logger = logging.getLogger(__name__)


class Embedder:
    """
    embedder that converts text to numbers.

    Example:
        embedder = Embedder()
        numbers = embedder.embed("hello world")
        # Returns: [0.234, -0.123, 0.456, ... ] (384 numbers)
    """

    def __init__(self):
        """Initialize the embedder (loads model when first used)."""
        self._model = None
        logger.info("Embedder created")

    def _load_model(self):
        """Load the embedding model (only when needed)."""
        if self._model is not None:
            return  # Already loaded

        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model...")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model loaded (384 dimensions)")

        except ImportError:
            logger.error("sentence-transformers not installed")
            raise ImportError(
                "Please install: pip install sentence-transformers"
            )

    def embed(self, text: str) -> list:
        """
        Convert text to a vector (list of numbers).

        Args:
            text: The text to convert (e.g., YAML content)

        Returns:
            List of 384 numbers representing the text

        Example:
            >>> embedder = Embedder()
            >>> vector = embedder.embed("insurance validation agent")
            >>> len(vector)
            384
        """
        self._load_model()

        # Convert text to vector
        vector = self._model.encode(text)

        # Convert to regular Python list
        return vector.tolist()

    def get_dimension(self) -> int:
        """
        Get the size of the vectors.

        Returns:
            384 (the number of dimensions)
        """
        self._load_model()
        return self._model.get_sentence_embedding_dimension()
