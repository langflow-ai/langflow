import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logger = logging.getLogger(__name__)


class QdrantDB:
    """
    Simple wrapper for Qdrant operations.

    Handles connecting, storing, searching, and retrieving documents.
    """

    def __init__(self, url: str, api_key: str = None):
        """
        Initialize Qdrant connection.

        Args:
            url: Your Qdrant URL (e.g., "https://xxxxx.qdrant.io")
            api_key: Your API key
        """
        self.url = url
        self.api_key = api_key
        self.client = None
        logger.info(f"QdrantDB initialized with URL: {url}")

    def connect(self) -> bool:
        """
        Connect to Qdrant.

        Returns:
            True if connected, False if failed
        """
        try:
            logger.info("Connecting to Qdrant...")
            self.client = QdrantClient(url=self.url, api_key=self.api_key)

            # Test connection
            collections = self.client.get_collections()
            logger.info(f"Connected! Found {len(collections.collections)} collections")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def create_collection(self, name: str, vector_size: int) -> bool:
        """
        Create a collection (like a table in database).

        Args:
            name: Collection name (e.g., "flow_yaml")
            vector_size: Size of vectors (e.g., 384)

        Returns:
            True if created/exists, False if failed
        """
        try:
            # Check if already exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if name in collection_names:
                logger.info(f"Collection '{name}' already exists")
                return True

            # Create new collection
            logger.info(f"Creating collection '{name}'...")
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE  # Cosine similarity
                ),
            )
            logger.info(f"Collection '{name}' created")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False

    def store(self, collection: str, doc_id: str, vector: list, data: dict) -> bool:
        """
        Store a document with its vector.

        Args:
            collection: Collection name
            doc_id: Document ID (must be UUID or integer)
            vector: The embedding vector
            data: The data to store (name, description, yaml, etc.)

        Returns:
            True if stored, False if failed
        """
        try:
            # Create a point (Qdrant's name for a document)
            point = PointStruct(
                id=doc_id,
                vector=vector,
                payload=data  # All your data goes here
            )

            # Store it
            self.client.upsert(
                collection_name=collection,
                points=[point]
            )

            logger.info(f"Stored document '{doc_id}'")
            return True

        except Exception as e:
            logger.error(f"Failed to store: {e}")
            return False

    def search(self, collection: str, vector: list, limit: int = 5) -> list:
        """
        Search for similar documents.

        Args:
            collection: Collection name
            vector: Query vector
            limit: Max number of results

        Returns:
            List of results with scores and data
        """
        try:
            # Search
            results = self.client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit,
                with_payload=True  # Include the data
            )

            # Format results
            formatted = []
            for result in results:
                formatted.append({
                    "id": result.id,
                    "score": result.score,  # 0-1, higher is better
                    "data": result.payload  # All the stored data
                })

            logger.info(f"Found {len(formatted)} results")
            return formatted

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get(self, collection: str, doc_id: str) -> dict:
        """
        Get a specific document by ID.

        Args:
            collection: Collection name
            doc_id: Document ID

        Returns:
            The document data, or None if not found
        """
        try:
            points = self.client.retrieve(
                collection_name=collection,
                ids=[doc_id],
                with_payload=True
            )

            if not points:
                logger.warning(f"Document '{doc_id}' not found")
                return None

            return points[0].payload

        except Exception as e:
            logger.error(f"Get failed: {e}")
            return None

    def delete(self, collection: str, doc_id: str) -> bool:
        """
        Delete a document.

        Args:
            collection: Collection name
            doc_id: Document ID to delete

        Returns:
            True if deleted, False if failed
        """
        try:
            self.client.delete(
                collection_name=collection,
                points_selector=[doc_id]
            )
            logger.info(f"Deleted document '{doc_id}'")
            return True

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
