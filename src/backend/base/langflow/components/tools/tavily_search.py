from enum import Enum

import httpx
from langchain.tools import StructuredTool
from langchain_core.tools import ToolException
from loguru import logger
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.schema import Data


class TavilySearchDepth(Enum):
    BASIC = "basic"
    ADVANCED = "advanced"


class TavilySearchTopic(Enum):
    GENERAL = "general"
    NEWS = "news"


class TavilySearchSchema(BaseModel):
    query: str = Field(..., description="The search query you want to execute with Tavily.")
    search_depth: TavilySearchDepth = Field(TavilySearchDepth.BASIC, description="The depth of the search.")
    topic: TavilySearchTopic = Field(TavilySearchTopic.GENERAL, description="The category of the search.")
    max_results: int = Field(5, description="The maximum number of search results to return.")
    include_images: bool = Field(default=False, description="Include a list of query-related images in the response.")
    include_answer: bool = Field(default=False, description="Include a short answer to original query.")


class TavilySearchToolComponent(LCToolComponent):
    display_name = "Tavily AI Search"
    description = """**Tavily AI** is a search engine optimized for LLMs and RAG, \
        aimed at efficient, quick, and persistent search results. It can be used independently or as an agent tool.

Note: Check 'Advanced' for all options.
"""
    icon = "TavilyIcon"
    name = "TavilyAISearch"
    documentation = "https://docs.tavily.com/"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Tavily API Key",
            required=True,
            info="Your Tavily API Key.",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query you want to execute with Tavily.",
        ),
        DropdownInput(
            name="search_depth",
            display_name="Search Depth",
            info="The depth of the search.",
            options=list(TavilySearchDepth),
            value=TavilySearchDepth.ADVANCED,
            advanced=True,
        ),
        DropdownInput(
            name="topic",
            display_name="Search Topic",
            info="The category of the search.",
            options=list(TavilySearchTopic),
            value=TavilySearchTopic.GENERAL,
            advanced=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="The maximum number of search results to return.",
            value=5,
            advanced=True,
        ),
        BoolInput(
            name="include_images",
            display_name="Include Images",
            info="Include a list of query-related images in the response.",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="include_answer",
            display_name="Include Answer",
            info="Include a short answer to original query.",
            value=True,
            advanced=True,
        ),
    ]

    def run_model(self) -> list[Data]:
        # Convert string values to enum instances with validation
        try:
            search_depth_enum = (
                self.search_depth
                if isinstance(self.search_depth, TavilySearchDepth)
                else TavilySearchDepth(str(self.search_depth).lower())
            )
        except ValueError as e:
            error_message = f"Invalid search depth value: {e!s}"
            self.status = error_message
            return [Data(data={"error": error_message})]

        try:
            topic_enum = (
                self.topic if isinstance(self.topic, TavilySearchTopic) else TavilySearchTopic(str(self.topic).lower())
            )
        except ValueError as e:
            error_message = f"Invalid topic value: {e!s}"
            self.status = error_message
            return [Data(data={"error": error_message})]

        return self._tavily_search(
            self.query,
            search_depth=search_depth_enum,
            topic=topic_enum,
            max_results=self.max_results,
            include_images=self.include_images,
            include_answer=self.include_answer,
        )

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="tavily_search",
            description="Perform a web search using the Tavily API.",
            func=self._tavily_search,
            args_schema=TavilySearchSchema,
        )

    def _tavily_search(
        self,
        query: str,
        *,
        search_depth: TavilySearchDepth = TavilySearchDepth.BASIC,
        topic: TavilySearchTopic = TavilySearchTopic.GENERAL,
        max_results: int = 5,
        include_images: bool = False,
        include_answer: bool = False,
    ) -> list[Data]:
        # Validate enum values
        if not isinstance(search_depth, TavilySearchDepth):
            msg = f"Invalid search_depth value: {search_depth}"
            raise TypeError(msg)
        if not isinstance(topic, TavilySearchTopic):
            msg = f"Invalid topic value: {topic}"
            raise TypeError(msg)

        try:
            url = "https://api.tavily.com/search"
            headers = {
                "content-type": "application/json",
                "accept": "application/json",
            }
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": search_depth.value,
                "topic": topic.value,
                "max_results": max_results,
                "include_images": include_images,
                "include_answer": include_answer,
            }

            with httpx.Client() as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            search_results = response.json()

            data_results = [
                Data(
                    data={
                        "title": result.get("title"),
                        "url": result.get("url"),
                        "content": result.get("content"),
                        "score": result.get("score"),
                    }
                )
                for result in search_results.get("results", [])
            ]

            if include_answer and search_results.get("answer"):
                data_results.insert(0, Data(data={"answer": search_results["answer"]}))

            if include_images and search_results.get("images"):
                data_results.append(Data(data={"images": search_results["images"]}))

            self.status = data_results  # type: ignore[assignment]

        except httpx.HTTPStatusError as e:
            error_message = f"HTTP error: {e.response.status_code} - {e.response.text}"
            logger.debug(error_message)
            self.status = error_message
            raise ToolException(error_message) from e
        except Exception as e:
            error_message = f"Unexpected error: {e}"
            logger.opt(exception=True).debug("Error running Tavily Search")
            self.status = error_message
            raise ToolException(error_message) from e
        return data_results
