from typing import Any, Dict, List

from pydantic.v1 import SecretStr

from langchain.chains import ConversationalRetrievalChain
from langchain_community.retrievers.needle import NeedleRetriever
from langchain_openai import ChatOpenAI

from langflow.custom.custom_component.component import Component
from langflow.io import (
    SecretStrInput,
    StrInput,
    DropdownInput,
    Output,
)
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER


class NeedleComponent(Component):
    display_name = "Needle Retriever"
    description = (
        "A retriever that uses the Needle API to search collections "
        "and generates responses using OpenAI."
    )
    documentation = "https://docs.needle-ai.com"
    icon = "search"
    name = "needle"

    inputs = [
        SecretStrInput(
            name="needle_api_key",
            display_name="Needle API Key",
            info="Your Needle API key.",
            required=True,
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="Your OpenAI API key.",
            required=True,
        ),
        StrInput(
            name="collection_id",
            display_name="Collection ID",
            info="The ID of the Needle collection.",
            required=True,
        ),
        StrInput(
            name="query",
            display_name="User Query",
            info="Enter your question here.",
            required=True,
        ),
        DropdownInput(
            name="output_type",
            display_name="Output Type",
            info="Return either the answer or the chunks.",
            options=["answer", "chunks"],
            value="answer",
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Result",
            name="result",
            type_="Message",
            method="run"
        )
    ]

    def run(self) -> Message:
        needle_api_key = SecretStr(self.needle_api_key).get_secret_value() if self.needle_api_key else ""
        openai_api_key = SecretStr(self.openai_api_key).get_secret_value() if self.openai_api_key else ""
        collection_id = self.collection_id
        query = self.query
        output_type = self.output_type

        # Validate inputs
        if not needle_api_key.strip():
            raise ValueError("The Needle API key cannot be empty.")
        if not openai_api_key.strip():
            raise ValueError("The OpenAI API key cannot be empty.")
        if not collection_id.strip():
            raise ValueError("The Collection ID cannot be empty.")
        if not query.strip():
            raise ValueError("The query cannot be empty.")

        # Handle output_type if it's somehow a list
        if isinstance(output_type, list):
            output_type = output_type[0]

        try:
            # Initialize the retriever
            retriever = NeedleRetriever(
                needle_api_key=needle_api_key,
                collection_id=collection_id,
            )

            # Create the chain
            llm = ChatOpenAI(
                temperature=0.7,
                api_key=openai_api_key,
            )

            qa_chain = ConversationalRetrievalChain.from_llm(
                llm=llm,
                retriever=retriever,
                return_source_documents=True,
            )

            # Process the query
            result = qa_chain({"question": query, "chat_history": []})
            
            # Format source documents
            docs = result["source_documents"]
            context = "\n\n".join([
                f"Document {i+1}:\n{doc.page_content}"
                for i, doc in enumerate(docs)
            ])

            # Create the text content
            text_content = (
                f"Question: {query}\n\n"
                f"Context:\n{context}\n\n"
                f"Answer: {result['answer']}"
            )

            # Create a Message object following chat.py pattern
            return Message(
                text=text_content,
                type="assistant",
                sender=MESSAGE_SENDER_AI,
                additional_kwargs={
                    "source_documents": [
                        {
                            "page_content": doc.page_content,
                            "metadata": doc.metadata
                        } for doc in docs
                    ]
                }
            )

        except Exception as e:
            raise ValueError(f"Error processing query: {e}") from e
