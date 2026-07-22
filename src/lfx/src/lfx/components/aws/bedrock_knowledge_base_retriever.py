"""Amazon Bedrock Knowledge Base Retriever component for Langflow.

Exposes the langchain-aws AmazonKnowledgeBasesRetriever as a dedicated Langflow node.
"""

from langflow.custom import Component
from langflow.io import BoolInput, IntInput, MessageTextInput, Output, SecretStrInput
from langflow.schema import Data


def _get_source_uri(result: dict) -> str:
    """Extract source URI from a retrieval result, handling all location types."""
    location = result.get("location", {})
    loc_type = location.get("type", "")
    if loc_type == "S3" or "s3Location" in location:
        return location.get("s3Location", {}).get("uri", "")
    if loc_type == "WEB" or "webLocation" in location:
        return location.get("webLocation", {}).get("url", "")
    if "confluenceLocation" in location:
        return location.get("confluenceLocation", {}).get("url", "")
    if "salesforceLocation" in location:
        return location.get("salesforceLocation", {}).get("url", "")
    if "sharePointLocation" in location:
        return location.get("sharePointLocation", {}).get("url", "")
    if "customDocumentLocation" in location:
        return location.get("customDocumentLocation", {}).get("id", "")
    # Fallback to metadata._source_uri (for agentic results)
    return result.get("metadata", {}).get("_source_uri", "")


class BedrockKnowledgeBaseRetrieverComponent(Component):
    """Retrieves documents from an Amazon Bedrock Knowledge Base.

    Wraps langchain-aws's AmazonKnowledgeBasesRetriever as a dedicated Langflow node.
    Supports both Managed Knowledge Bases (recommended) and Vector search.
    """

    display_name = "Amazon Bedrock Knowledge Base"
    description = "Retrieve documents using langchain-aws AmazonKnowledgeBasesRetriever with managed or vector search."
    icon = "Amazon"
    name = "BedrockKnowledgeBaseRetriever"

    inputs = [
        MessageTextInput(
            name="knowledge_base_id",
            display_name="Knowledge Base ID",
            info="The ID of the Amazon Bedrock Knowledge Base (10 alphanumeric characters).",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="The search query to retrieve relevant documents.",
            required=True,
        ),
        BoolInput(
            name="use_agentic_retrieval",
            display_name="Use Agentic Retrieval",
            value=True,
            info=(
                "If enabled, tries AgenticRetrieveStream first (query decomposition + managed reranking)"
                " with fallback to standard Retrieve."
            ),
        ),
        MessageTextInput(
            name="region_name",
            display_name="AWS Region",
            value="us-east-1",
            info="AWS region where the Knowledge Base is located.",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            value=5,
            info="Maximum number of results to return.",
        ),
        SecretStrInput(
            name="aws_access_key_id",
            display_name="AWS Access Key ID",
            info="AWS access key. Optional if using IAM role or environment credentials.",
            required=False,
        ),
        SecretStrInput(
            name="aws_secret_access_key",
            display_name="AWS Secret Access Key",
            info="AWS secret key. Optional if using IAM role or environment credentials.",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Retrieved Documents", name="documents", method="retrieve"),
    ]

    def retrieve(self) -> list[Data]:
        """Retrieve documents using langchain-aws AmazonKnowledgeBasesRetriever."""
        use_agentic_retrieval = self.use_agentic_retrieval

        # Try agentic retrieval first
        if use_agentic_retrieval:
            try:
                import boto3
                from botocore.config import Config

                # Build credentials kwargs for boto3
                boto_kwargs: dict = {"region_name": self.region_name}
                if self.aws_access_key_id and self.aws_secret_access_key:
                    boto_kwargs["aws_access_key_id"] = self.aws_access_key_id
                    boto_kwargs["aws_secret_access_key"] = self.aws_secret_access_key

                client = boto3.client(
                    "bedrock-agent-runtime",
                    config=Config(user_agent_extra="langflow/bedrock-kb"),
                    **boto_kwargs,
                )
                response = client.agentic_retrieve_stream(
                    messages=[{"content": {"text": self.query}, "role": "user"}],
                    retrievers=[
                        {
                            "configuration": {
                                "knowledgeBase": {
                                    "knowledgeBaseId": self.knowledge_base_id,
                                    "retrievalOverrides": {"maxNumberOfResults": self.number_of_results},
                                }
                            }
                        }
                    ],
                    agenticRetrieveConfiguration={
                        "foundationModelType": "MANAGED",
                        "rerankingModelType": "MANAGED",
                    },
                )
                results = []
                for event in response.get("stream", []):
                    if "result" in event and "results" in event["result"]:
                        results.extend(
                            Data(
                                text=result.get("content", {}).get("text", ""),
                                data={
                                    "source": _get_source_uri(result),
                                    "score": result.get("score", 0.0),
                                    "knowledge_base_id": self.knowledge_base_id,
                                },
                            )
                            for result in event["result"]["results"]
                        )
                if results:
                    return results
            except Exception as e:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).debug("Agentic retrieval unavailable, falling back: %s", e)

        try:
            from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
        except ImportError as err:
            msg = "langchain-aws is required. Install with: pip install langchain-aws>=0.2.0"
            raise ImportError(msg) from err

        # Build retrieval config
        retrieval_config = {"managedSearchConfiguration": {"numberOfResults": self.number_of_results}}
        # Build credentials kwargs
        credentials_kwargs = {}
        if self.aws_access_key_id and self.aws_secret_access_key:
            credentials_kwargs["credentials_profile_name"] = None
            credentials_kwargs["aws_access_key_id"] = self.aws_access_key_id
            credentials_kwargs["aws_secret_access_key"] = self.aws_secret_access_key

        retriever = AmazonKnowledgeBasesRetriever(
            knowledge_base_id=self.knowledge_base_id,
            region_name=self.region_name,
            retrieval_config=retrieval_config,
            **credentials_kwargs,
        )

        docs = retriever.invoke(self.query)

        results = []
        for doc in docs:
            results.append(
                Data(
                    text=doc.page_content,
                    data={
                        "source": doc.metadata.get("source", ""),
                        "score": doc.metadata.get("score", 0.0),
                        "knowledge_base_id": self.knowledge_base_id,
                    },
                )
            )

        return results
