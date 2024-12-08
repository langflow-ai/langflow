from typing import Any

from langchain.chains import ConversationalRetrievalChain
from langchain_community.retrievers.needle import NeedleRetriever
from langchain_openai import ChatOpenAI

from langflow.custom import CustomComponent


class NeedleComponent(CustomComponent):
    display_name = "Needle Retriever"
    description = "A retriever that uses the Needle API to search collections and generates responses using OpenAI."
    documentation = "https://docs.needle-ai.com"
    icon = "search"
    name = "needle"

    def build_config(self) -> dict[str, Any]:
        """Build the UI configuration for the component."""
        return {
            "needle_api_key": {
                "display_name": "Needle API Key",
                "field_type": "password",
                "required": True,
            },
            "openai_api_key": {
                "display_name": "OpenAI API Key",
                "field_type": "password",
                "required": True,
            },
            "collection_id": {
                "display_name": "Collection ID",
                "required": True,
            },
            "query": {
                "display_name": "User Query",
                "field_type": "str",
                "required": True,
                "placeholder": "Enter your question here",
            },
            "output_type": {
                "display_name": "Output Type",
                "field_type": "select",
                "required": True,
                "options": ["answer", "chunks"],
                "value": "answer",
                "is_multi": False,
            },
            "top_k": {
                "display_name": "Top K",
                "field_type": "int",
                "value": 10,
                "required": False,
            },
            "code": {
                "show": False,
                "required": False,
            },
        }

    def build(
        self,
        needle_api_key: str,
        openai_api_key: str,
        collection_id: str,
        query: str,
        output_type: str = "answer",
        top_k: int = 10,
    ) -> str:
        """Build the NeedleRetriever component and process the query."""
        # Validate inputs
        if not needle_api_key.strip():
            msg = "The Needle API key cannot be empty."
            raise ValueError(msg)
        if not openai_api_key.strip():
            msg = "The OpenAI API key cannot be empty."
            raise ValueError(msg)
        if not collection_id.strip():
            msg = "The Collection ID cannot be empty."
            raise ValueError(msg)
        if not query.strip():
            msg = "The query cannot be empty."
            raise ValueError(msg)
        if top_k <= 0:
            msg = "Top K must be a positive integer."
            raise ValueError(msg)

        # Handle output_type if it's a list
        if isinstance(output_type, list):
            output_type = output_type[0]

        try:
            # Initialize the retriever
            retriever = NeedleRetriever(
                needle_api_key=needle_api_key,
                collection_id=collection_id,
                top_k=top_k,
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

            # Return based on output type
            if str(output_type).lower().strip() == "chunks":
                # Format the source documents for better readability
                docs = result["source_documents"]
                formatted_chunks = [f"Chunk {i+1}:\n{doc.page_content}\n" for i, doc in enumerate(docs)]
                return "\n".join(formatted_chunks)

            return result["answer"]

        except Exception as e:
            msg = f"Error processing query: {e!s}"
            raise ValueError(msg) from e
