from langflow.custom import Component
from langflow.inputs import SecretStrInput, StrInput, DataInput
from langflow.io import Output
from langflow.schema import Data
from astrapy import AstraDBAdmin, DataAPIClient
from typing import Dict, Any, List
import json

class TwelveLabsAstraUpload(Component):
    display_name = "Twelve Labs Astra Upload"
    description = "Upload Twelve Labs embeddings to Astra DB"
    documentation = "https://docs.langflow.org/"
    icon = "upload"
    name = "TwelveLabsAstraUpload"

    inputs = [
        DataInput(
            name="embeddings",
            display_name="Embeddings",
            info="Embeddings from Twelve Labs",
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
            info="Name of the collection to store embeddings",
            required=True
        ),
        StrInput(
            name="environment",
            display_name="Environment",
            info="The environment for the Astra DB API Endpoint",
            advanced=True
        )
    ]

    outputs = [
        Output(display_name="Status", name="status", method="upload_embeddings")
    ]

    def get_database_object(self):
        """Get AstraDB database object."""
        try:
            client = DataAPIClient(token=self.token, environment=self.environment)
            return client.get_database(
                api_endpoint=self.api_endpoint,
                token=self.token
            )
        except Exception as e:
            msg = f"Error connecting to AstraDB: {e}"
            raise ValueError(msg) from e

    def process_embeddings(self, embeddings_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process embeddings into documents for AstraDB."""
        documents = []
        
        # Extract embeddings from the data
        embeddings_list = embeddings_data.get("embeddings", [])
        
        for embedding_item in embeddings_list:
            # Handle video embeddings
            if "video_embedding" in embedding_item:
                if embedding_item["video_embedding"]:
                    documents.append({
                        "embedding": embedding_item["video_embedding"][:1000],  # First 1000 dimensions for vector search
                        "embedding_extra": embedding_item["video_embedding"][1000:],  # Remaining 24 dimensions
                        "metadata": {
                            "type": "video",
                            "scope": "video",
                            "file_path": embedding_item["file_path"],
                            "task_id": embedding_item["task_id"]
                        }
                    })
                
                # Process clip embeddings
                for idx, clip_embedding in enumerate(embedding_item.get("clip_embeddings", [])):
                    documents.append({
                        "embedding": clip_embedding[:1000],  # First 1000 dimensions for vector search
                        "embedding_extra": clip_embedding[1000:],  # Remaining 24 dimensions
                        "metadata": {
                            "type": "video",
                            "scope": "clip",
                            "clip_index": idx,
                            "file_path": embedding_item["file_path"],
                            "task_id": embedding_item["task_id"]
                        }
                    })
            
            # Handle text embeddings
            elif "embedding" in embedding_item:
                documents.append({
                    "embedding": embedding_item["embedding"][:1000],  # First 1000 dimensions for vector search
                    "embedding_extra": embedding_item["embedding"][1000:],  # Remaining 24 dimensions
                    "metadata": {
                        "type": "text",
                        "text": embedding_item["text"]
                    }
                })

        return documents

    def upload_embeddings(self) -> Data:
        """Upload embeddings to AstraDB."""
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
            
            # Process embeddings into documents
            documents = self.process_embeddings(embeddings_data)
            
            if not documents:
                return Data(value={"error": "No valid embeddings to upload"})

            # Upload documents in batches
            batch_size = 100
            total_uploaded = 0
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                collection.insert_many(batch)
                total_uploaded += len(batch)
                self.log(f"Uploaded {total_uploaded}/{len(documents)} embeddings")

            status = {
                "status": "success",
                "uploaded": total_uploaded,
                "collection": self.collection_name
            }
            
            return Data(value=status)

        except Exception as e:
            error_msg = f"Error uploading embeddings: {str(e)}"
            self.log(error_msg, "ERROR")
            return Data(value={"error": error_msg})
