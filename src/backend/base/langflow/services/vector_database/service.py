import logging
import os
from datetime import datetime

from langflow.services.vector_database.embedder import Embedder
from langflow.services.vector_database.qdrant import QdrantDB

logger = logging.getLogger(__name__)


class VectorDatabaseService:
    """
    Simple service for storing and searching agent flows.

    Example usage:
        # Initialize
        service = VectorDatabaseService()

        # Store a flow
        service.store_flow(
            flow_id="4e910e74-067e-44f9-988a-a0cff09dc57a",
            flow_name="EOC Validation Agent",
            yaml_content="...",
            description="Validates insurance coverage"
        )

        # Search for flows
        results = service.search_flows("insurance validation")
        for result in results:
            print(result["name"], result["score"])

        # Get specific flow
        flow = service.get_flow("4e910e74-067e-44f9-988a-a0cff09dc57a")
        print(flow["yaml_content"])
    """

    # Collection name where flows are stored
    COLLECTION_NAME = os.getenv("VECTOR_DB_COLLECTION")

    def __init__(self):
        """
        Initialize the service.

        Automatically reads QDRANT_URL and QDRANT_API_KEY from environment.
        """
        # Get Qdrant credentials from environment
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not qdrant_url:
            raise ValueError(
                "QDRANT_URL not found in environment. "
                "Please add it to your .env file."
            )

        # Create simple components
        self.embedder = Embedder()  # Converts text to numbers
        self.db = QdrantDB(qdrant_url, qdrant_api_key)  # Talks to Qdrant

        self._initialized = False
        logger.info("VectorDatabaseService created")

    def initialize(self) -> bool:
        """
        Connect to Qdrant and create collection if needed.

        This is called automatically on first use.

        Returns:
            True if successful, False if failed
        """
        if self._initialized:
            return True

        try:
            logger.info("Initializing service...")

            # Step 1: Connect to Qdrant
            if not self.db.connect():
                logger.error("Failed to connect to Qdrant")
                return False

            # Step 2: Create collection if it doesn't exist
            vector_size = self.embedder.get_dimension()  # 384
            if not self.db.create_collection(self.COLLECTION_NAME, vector_size):
                logger.error("Failed to create collection")
                return False

            self._initialized = True
            logger.info("Service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    def store_flow(
        self,
        flow_id: str,
        flow_name: str,
        yaml_content: str,
        description: str = "",
        components: list = None,
        tags: list = None
    ) -> bool:
        """
        Store a flow in the vector database.

        Args:
            flow_id: Unique flow ID (UUID format)
            flow_name: Name of the flow
            yaml_content: The YAML specification
            description: Flow description
            components: List of component types (optional)
            tags: Tags for filtering (optional)

        Returns:
            True if stored successfully, False otherwise

        Example:
            success = service.store_flow(
                flow_id="4e910e74-067e-44f9-988a-a0cff09dc57a",
                flow_name="EOC Validation Agent",
                yaml_content="id: ...\ncomponents: ...",
                description="Validates insurance coverage",
                components=["PromptComponent", "AgentComponent"],
                tags=["healthcare", "insurance"]
            )
        """
        # Initialize if needed
        if not self._initialized:
            if not self.initialize():
                return False

        try:
            logger.info(f"Storing flow: {flow_name}")

            # Step 1: Convert text to vector
            # We combine name + description + yaml for better search
            text_to_embed = f"{flow_name}\n{description}\n{yaml_content}"
            vector = self.embedder.embed(text_to_embed)

            # Step 2: Prepare data to store
            data = {
                "flow_id": flow_id,
                "name": flow_name,
                "description": description,
                "yaml_content": yaml_content,
                "components": components or [],
                "tags": tags or [],
                "created_at": datetime.utcnow().isoformat(),
                "yaml_length": len(yaml_content)
            }

            # Step 3: Store in Qdrant
            success = self.db.store(
                collection=self.COLLECTION_NAME,
                doc_id=flow_id,
                vector=vector,
                data=data
            )

            if success:
                logger.info(f"✓ Stored flow: {flow_name}")
            else:
                logger.error(f"✗ Failed to store flow: {flow_name}")

            return success

        except Exception as e:
            logger.error(f"Error storing flow: {e}")
            return False

    def search_flows(
        self,
        query: str,
        limit: int = 5
    ) -> list:
        """
        Search for flows similar to your query.

        Uses semantic search - finds flows by meaning, not just keywords.

        Args:
            query: What you're looking for (e.g., "insurance validation agent")
            limit: Maximum number of results

        Returns:
            List of matching flows with scores

        Example:
            results = service.search_flows("validate insurance coverage", limit=5)

            for result in results:
                print(f"Name: {result['name']}")
                print(f"Score: {result['score']:.2f}")
                print(f"Description: {result['description']}")
                print()
        """
        # Initialize if needed
        if not self._initialized:
            if not self.initialize():
                return []

        try:
            logger.info(f"Searching for: '{query}'")

            # Step 1: Convert query to vector
            query_vector = self.embedder.embed(query)

            # Step 2: Search in Qdrant
            results = self.db.search(
                collection=self.COLLECTION_NAME,
                vector=query_vector,
                limit=limit
            )

            # Step 3: Format results nicely
            formatted = []
            for result in results:
                data = result["data"]
                formatted.append({
                    "flow_id": data.get("flow_id"),
                    "name": data.get("name"),
                    "description": data.get("description"),
                    "score": result["score"],  # 0-1, higher = better match
                    "components": data.get("components", []),
                    "tags": data.get("tags", []),
                    "yaml_preview": data.get("yaml_content", "")[:200] + "..."
                })

            logger.info(f"Found {len(formatted)} flows")
            return formatted

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_flow(self, flow_id: str) -> dict:
        """
        Get complete flow data by ID.

        Args:
            flow_id: The flow UUID

        Returns:
            Flow data including full YAML, or None if not found

        Example:
            flow = service.get_flow("4e910e74-067e-44f9-988a-a0cff09dc57a")

            if flow:
                print(f"Name: {flow['name']}")
                print(f"YAML:\n{flow['yaml_content']}")
        """
        # Initialize if needed
        if not self._initialized:
            if not self.initialize():
                return None

        try:
            logger.info(f"Getting flow: {flow_id}")

            data = self.db.get(
                collection=self.COLLECTION_NAME,
                doc_id=flow_id
            )

            if data:
                logger.info(f"✓ Found flow: {data.get('name')}")
            else:
                logger.warning(f"✗ Flow not found: {flow_id}")

            return data

        except Exception as e:
            logger.error(f"Get flow failed: {e}")
            return None

    def delete_flow(self, flow_id: str) -> bool:
        """
        Delete a flow from the database.

        Args:
            flow_id: The flow UUID to delete

        Returns:
            True if deleted, False if failed

        Example:
            success = service.delete_flow("4e910e74-067e-44f9-988a-a0cff09dc57a")
        """
        # Initialize if needed
        if not self._initialized:
            if not self.initialize():
                return False

        try:
            logger.info(f"Deleting flow: {flow_id}")

            success = self.db.delete(
                collection=self.COLLECTION_NAME,
                doc_id=flow_id
            )

            if success:
                logger.info(f"✓ Deleted flow: {flow_id}")
            else:
                logger.error(f"✗ Failed to delete flow: {flow_id}")

            return success

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False
