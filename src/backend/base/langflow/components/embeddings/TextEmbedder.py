from langflow.custom import Component
from langflow.io import HandleInput, MessageInput, Output
from langflow.field_typing import Embeddings
from langflow.schema.message import Message
from langflow.schema import Data


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
        embedding_model: Embeddings = self.embedding_model
        message: Message = self.message

        # Extract the text content from the message
        text_content = message.text

        # Generate embeddings using the provided embedding model
        embeddings = embedding_model.embed_documents([text_content])

        # Assuming the embedding model returns a list of embeddings, we take the first one
        if embeddings:
            embedding_vector = embeddings[0]
        else:
            embedding_vector = []

        # Create a Data object to encapsulate the results
        result_data = Data(data={"text": text_content, "embeddings": embedding_vector})

        self.status = {"text": text_content, "embeddings": embedding_vector}
        return result_data
