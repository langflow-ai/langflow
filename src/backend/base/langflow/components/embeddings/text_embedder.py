import logging
from typing import TYPE_CHECKING

from langflow.custom.custom_component.component import Component
from langflow.io import HandleInput, MessageInput, Output
from langflow.schema.data import Data

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
            required=True,
        ),
        MessageInput(
            name="message",
            display_name="Message",
            info="The message to generate embeddings for.",
            required=True,
        ),
    ]
    outputs = [
        Output(display_name="Embedding Data", name="embeddings", method="generate_embeddings"),
    ]

    def generate_embeddings(self) -> Data:
        try:
            embedding_model: Embeddings = self.embedding_model
            message: Message = self.message

            # Combine validation checks to reduce nesting
            if not embedding_model or not hasattr(embedding_model, "embed_documents"):
                msg = "Invalid or incompatible embedding model"
                raise ValueError(msg)

            text_content = message.text if message and message.text else ""
            if not text_content:
                msg = "No text content found in message"
                raise ValueError(msg)

            embeddings = embedding_model.embed_documents([text_content])
            if not embeddings or not isinstance(embeddings, list):
                msg = "Invalid embeddings generated"
                raise ValueError(msg)

            embedding_vector = embeddings[0]
            self.status = {"text": text_content, "embeddings": embedding_vector}
            return Data(data={"text": text_content, "embeddings": embedding_vector})
        except Exception as e:
            logging.exception("Error generating embeddings")
            error_data = Data(data={"text": "", "embeddings": [], "error": str(e)})
            self.status = {"error": str(e)}
            return error_data
