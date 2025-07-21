from langchain_community.retrievers.needle import NeedleRetriever

from langflow.custom.custom_component.component import Component
from langflow.io import IntInput, MessageTextInput, Output, SecretStrInput
from langflow.schema.message import Message
from langflow.utils.constants import MESSAGE_SENDER_AI


class NeedleComponent(Component):
    display_name = "Needle Retriever"
    description = "A retriever that uses the Needle API to search collections."
    documentation = "https://docs.needle-ai.com"
    icon = "Needle"
    name = "needle"

    inputs = [
        SecretStrInput(
            name="needle_api_key",
            display_name="Needle API Key",
            info="Your Needle API key.",
            required=True,
        ),
        MessageTextInput(
            name="collection_id",
            display_name="Collection ID",
            info="The ID of the Needle collection.",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="User Query",
            info="Enter your question here. In tool mode, you can also specify top_k parameter (min: 20).",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K Results",
            info="Number of search results to return (min: 20).",
            value=20,
            required=True,
        ),
    ]

    outputs = [Output(display_name="Result", name="result", type_="Message", method="run")]

    def run(self) -> Message:
        # Extract query and top_k
        query_input = self.query
        actual_query = query_input.get("query", "") if isinstance(query_input, dict) else query_input

        # Parse top_k from tool input or use default, always enforcing minimum of 20
        try:
            if isinstance(query_input, dict) and "top_k" in query_input:
                agent_top_k = query_input.get("top_k")
                # Check if agent_top_k is not None before converting to int
                top_k = max(20, int(agent_top_k)) if agent_top_k is not None else max(20, self.top_k)
            else:
                top_k = max(20, self.top_k)
        except (ValueError, TypeError):
            top_k = max(20, self.top_k)

        # Validate required inputs
        if not self.needle_api_key or not self.needle_api_key.strip():
            error_msg = "The Needle API key cannot be empty."
            raise ValueError(error_msg)
        if not self.collection_id or not self.collection_id.strip():
            error_msg = "The Collection ID cannot be empty."
            raise ValueError(error_msg)
        if not actual_query or not actual_query.strip():
            error_msg = "The query cannot be empty."
            raise ValueError(error_msg)

        try:
            # Initialize the retriever and get documents
            retriever = NeedleRetriever(
                needle_api_key=self.needle_api_key,
                collection_id=self.collection_id,
                top_k=top_k,
            )

            docs = retriever.get_relevant_documents(actual_query)

            # Format the response
            if not docs:
                text_content = "No relevant documents found for the query."
            else:
                context = "\n\n".join([f"Document {i + 1}:\n{doc.page_content}" for i, doc in enumerate(docs)])
                text_content = f"Question: {actual_query}\n\nContext:\n{context}"

            # Return formatted message
            return Message(
                text=text_content,
                type="assistant",
                sender=MESSAGE_SENDER_AI,
                additional_kwargs={
                    "source_documents": [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in docs],
                    "top_k_used": top_k,
                },
            )

        except Exception as e:
            error_msg = f"Error processing query: {e!s}"
            raise ValueError(error_msg) from e
