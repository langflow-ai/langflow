import logging
from typing import TYPE_CHECKING

from langflow.custom import Component
from langflow.io import HandleInput, MessageInput, Output
from langflow.schema import Data

if TYPE_CHECKING:
    from langflow.field_typing import Embeddings
    from langflow.schema.message import Message


class TextEmbedderComponent(Component):
    display_name: str = "Text Embedder"
    description: str = "Generate embeddings for a given message using the specified embedding model."
    icon = "binary"
    inputs = [
        HandleInput(
            name="embedding_model",
            display_name="Embedding Model",
            info="The embedding model to use for generating embeddings.",
            input_types=["Embeddings"],
        ),
        MessageInput(
            name="message",
            display_name="Message",
            info="The message to generate embeddings for.",
        ),
    ]
    outputs = [
        Output(display_name="Embedding Data", name="embeddings", method="generate_embeddings"),
    ]

    def generate_embeddings(self) -> Data:
        try:
            embedding_model: Embeddings = self.embedding_model
            message: Message = self.message

            # Validate embedding model
            if not embedding_model:
                msg = "Embedding model not provided"
                raise ValueError(msg)

            # Extract the text content from the message
            text_content = message.text if message and message.text else ""
            if not text_content:
                msg = "No text content found in message"
                raise ValueError(msg)

            # Check if the embedding model has the required attributes
            if not hasattr(embedding_model, "client") or not embedding_model.client:
                msg = "Embedding model client not properly initialized"
                raise ValueError(msg)

            # Ensure the base URL has proper protocol
            if hasattr(embedding_model.client, "base_url"):
                base_url = embedding_model.client.base_url
                if not base_url.startswith(("http://", "https://")):
                    embedding_model.client.base_url = f"https://{base_url}"

            # Generate embeddings using the provided embedding model
            embeddings = embedding_model.embed_documents([text_content])

            # Validate embeddings output
            if not embeddings or not isinstance(embeddings, list):
                msg = "Invalid embeddings generated"
                raise ValueError(msg)

            embedding_vector = embeddings[0]

        except Exception as e:
            logging.exception("Error generating embeddings")
            # Return empty data with error status
            error_data = Data(data={"text": "", "embeddings": [], "error": str(e)})
            self.status = {"error": str(e)}
            return error_data

        # Create a Data object to encapsulate the results
        result_data = Data(data={"text": text_content, "embeddings": embedding_vector})
        self.status = {"text": text_content, "embeddings": embedding_vector}
        return result_data
