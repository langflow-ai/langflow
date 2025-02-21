from langflow.custom import Component
from langflow.inputs import SecretStrInput, StrInput, DataInput, IntInput
from langflow.io import Output
from langflow.schema import Data
from astrapy import DataAPIClient
from typing import Dict, Any, List

class TwelveLabsAstraSearch(Component):
    display_name = "Twelve Labs Astra Search"
    description = "Search Twelve Labs embeddings in Astra DB using vector similarity"
    documentation = "https://docs.langflow.org/"
    icon = "search"
    name = "TwelveLabsAstraSearch"

    inputs = [
        DataInput(
            name="embeddings",
            display_name="Embeddings",
            info="Embeddings from Twelve Labs to search with",
            required=True
        ),
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB",
            required=True
        ),
        StrInput(
            name="api_endpoint",
            display_name="Astra DB API Endpoint",
            info="The API Endpoint for the Astra DB instance",
            required=True
        ),
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            info="Name of the collection to search embeddings",
            required=True
        ),
        IntInput(
            name="limit",
            display_name="Result Limit",
            info="Maximum number of results to return",
            value=10
        )
    ]

    outputs = [
        Output(display_name="Results", name="results", method="search_embeddings")
    ]

    def get_database_object(self):
        """Get AstraDB database object."""
        try:
            client = DataAPIClient(token=self.token)
            database = client.get_database(
                api_endpoint=self.api_endpoint,
                token=self.token
            )
            return database
        except Exception as e:
            msg = f"Error connecting to AstraDB: {e}"
            raise ValueError(msg) from e

    def search_embeddings(self) -> Data:
        """Search for similar embeddings in AstraDB."""
        try:
            # Validate inputs
            if not self.embeddings or not isinstance(self.embeddings, Data):
                return Data(value={"error": "No embeddings data provided"})

            embeddings_data = self.embeddings.value
            if not embeddings_data:
                return Data(value={"error": "Empty embeddings data"})

            # Get database and collection
            database = self.get_database_object()
            collection = database.get_collection(self.collection_name)
            
            # Extract the query embeddings
            query_embeddings = embeddings_data.get("embeddings", [])
            if not query_embeddings:
                return Data(value={"error": "No embeddings found in input data"})

            query_results = []
            # Search for each embedding vector
            for query_item in query_embeddings:
                query_vector = query_item.get("embedding")
                if not query_vector:
                    continue

                # Perform vector similarity search using $vector operator
                search_results = collection.find(
                    filter={},
                    sort={"$vector": query_vector},
                    limit=self.limit,
                    projection={"task_id": True, "type": True, "scope": True, "file_path": True, "clip_index": True, "content": True}
                )

                # Process results for this query
                query_matches = []
                for result in search_results:
                    if "$vector" in result:
                        del result["$vector"]
                    query_matches.append(result)

                # Add this query's results to the list
                query_results.append({
                    "query_text": query_item.get("text", ""),
                    "matches": query_matches,
                    "count": len(query_matches)
                })

            return Data(value={
                "status": "success",
                "results": query_results,
                "total_queries": len(query_results)
            })

        except Exception as e:
            error_msg = f"Error searching embeddings: {str(e)}"
            self.log(error_msg, "ERROR")
            return Data(value={"error": error_msg})
