from loguru import logger
from typing import Any

from langchain_community.retrievers.needle import NeedleRetriever
from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel
from pydantic.v1 import Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import SecretStrInput, StrInput
from langflow.schema import Data


class NeedleSearchKnowledgeBaseSchema(BaseModel):
    """Schema for the Needle Search Knowledge Base tool."""
    query: str = Field(..., description="The search query to find relevant information in the knowledge base")
    top_k: int = Field(20, description="Maximum number of search results to return (min: 20)")


class NeedleKnowledgeBaseWrapper(BaseModel):
    """Wrapper around Needle Knowledge Base Search."""
    needle_api_key: str
    collection_id: str
    verbose: bool = False

    def _prepare_retriever(self, top_k: int = 20) -> NeedleRetriever:
        return NeedleRetriever(
            needle_api_key=self.needle_api_key,
            collection_id=self.collection_id,
            top_k=top_k,
        )

    def results(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        # Enforce a minimum top_k value
        top_k = max(20, top_k)
        if self.verbose:
            self._log_search_start(query, top_k)

        retriever = self._prepare_retriever(top_k=top_k)
        results = retriever.get_relevant_documents(query)

        if not results:
            error_msg = "No results found"
            raise AssertionError(error_msg)

        processed_results = []
        for idx, doc in enumerate(results, 1):
            metadata = getattr(doc, "metadata", {})
            snippet_lines = [
                f"### Result {idx}",
                "",
                doc.page_content,
                "",
            ]
            if metadata:
                snippet_lines.append("**Metadata:**")
                snippet_lines.extend(f"- {key}: {value}" for key, value in metadata.items())
                snippet_lines.append("")
            content = "\n".join(snippet_lines)
            processed_results.append({
                "page_content": doc.page_content,
                "metadata": metadata,
                "snippets": [{"text": content}],
                "formatted_content": content,
            })

        summary_text = (
            f"### Search Results Summary\n\n"
            f"Found {len(results)} relevant results for query: '{query}'\n"
        )
        summary = {
            "page_content": f"Found {len(results)} relevant results for query: {query}",
            "metadata": {"type": "summary"},
            "snippets": [{"text": summary_text}],
            "formatted_content": summary_text,
        }
        return [summary, *processed_results]

    def run(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        top_k = kwargs.get("top_k", 20)
        if self.verbose:
            self._log_query_start(query, top_k)

        try:
            results = self.results(query, top_k=top_k)
            if self.verbose:
                self._log_results_found(len(results) - 1)
        except Exception as e:
            error_msg = f"Search failed: {e}"
            raise ToolException(error_msg) from e
        
        return results

    def _log_search_start(self, query: str, top_k: int) -> None:
        """Log the start of a search operation."""
        if self.verbose:
            logger.info("Searching: '%s' with top_k=%d", query, top_k)

    def _log_query_start(self, query: str, top_k: int) -> None:
        """Log the start of a query operation."""
        if self.verbose:
            logger.info("Query: '%s' with top_k=%d", query, top_k)

    def _log_results_found(self, count: int) -> None:
        """Log the number of results found."""
        if self.verbose:
            logger.info("Found %d documents", count)


class NeedleSearchKnowledgeBaseComponent(LCToolComponent):
    display_name = "Needle Search KB"
    description = "Search your knowledge base using Needle"
    name = "NeedleKnowledgeBase"
    icon = "Needle"

    # Only expose the configuration inputs in the UI
    inputs = [
        SecretStrInput(
            name="needle_api_key",
            display_name="Needle API Key",
            required=True,
        ),
        StrInput(
            name="collection_id",
            display_name="Collection ID",
            required=True,
        ),
    ]

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper(
            needle_api_key=self.needle_api_key,
            collection_id=self.collection_id,
        )
        tool = StructuredTool.from_function(
            name="needle_search_knowledge_base",
            description=(
                "This tool retrieves information from your knowledge base containing unstructured data, "
                "such as text, tables, invoices, reports, and emails.\n\n"
                "Args:\n"
                "    query (str): The search query to find relevant information in the knowledge base\n"
                "    top_k (int): Number of top results to return (min: 20, max: 200)"
            ),
            func=wrapper.run,
            args_schema=NeedleSearchKnowledgeBaseSchema,
        )
        self.status = "Needle Knowledge Base Search Tool"
        return tool

    def run_model(self) -> list[Data]:
        error_msg = "This tool is meant to be used by an agent, not called directly."
        raise NotImplementedError(error_msg)

    def _build_wrapper(self, needle_api_key: str, collection_id: str) -> NeedleKnowledgeBaseWrapper:
        return NeedleKnowledgeBaseWrapper(
            needle_api_key=needle_api_key,
            collection_id=collection_id,
        )
