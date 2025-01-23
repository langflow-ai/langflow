import httpx
import requests

from langflow.custom import Component
from langflow.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.io import Output
from langflow.schema import DataFrame


class TavilySearchComponent(Component):
    """Component for performing searches using the Tavily AI Search API.

    This component allows users to search using Tavily AI and returns results
    in a DataFrame format. It supports customization of search parameters
    and provides detailed search options.
    """

    display_name = "Tavily AI Search"
    description = """**Tavily AI** is a search engine optimized for LLMs and RAG, \
        aimed at efficient, quick, and persistent search results."""
    icon = "TavilyIcon"

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
            tool_mode=True,
            required=True,
        ),
        DropdownInput(
            name="search_depth",
            display_name="Search Depth",
            info="The depth of the search.",
            options=["basic", "advanced"],
            value="advanced",
            advanced=True,
        ),
        DropdownInput(
            name="topic",
            display_name="Search Topic",
            info="The category of the search.",
            options=["general", "news"],
            value="general",
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

    outputs = [
        Output(
            display_name="Results",
            name="results",
            type_=DataFrame,
            method="search_tavily",
        ),
    ]

    def search_tavily(self) -> DataFrame:
        """Search using Tavily AI and return results as a DataFrame."""
        if not self.api_key:
            return DataFrame([{"error": "Invalid Tavily API Key"}])

        try:
            url = "https://api.tavily.com/search"
            headers = {
                "content-type": "application/json",
                "accept": "application/json",
            }
            payload = {
                "api_key": self.api_key,
                "query": self.query,
                "search_depth": self.search_depth,
                "topic": self.topic,
                "max_results": self.max_results,
                "include_images": self.include_images,
                "include_answer": self.include_answer,
            }

            with httpx.Client() as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            search_results = response.json()

            # Prepare results
            results = []

            # Add answer if included
            if self.include_answer and search_results.get("answer"):
                results.append({"type": "answer", "content": search_results["answer"]})

            # Add search results
            results.extend(
                [
                    {
                        "type": "search_result",
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "score": result.get("score", 0),
                    }
                    for result in search_results.get("results", [])
                ]
            )

            # Add images if included
            if self.include_images and search_results.get("images"):
                results.append({"type": "images", "images": search_results["images"]})

            return DataFrame(results)

        except (httpx.HTTPStatusError, requests.HTTPError) as exc:
            error_message = f"HTTP error occurred: {exc}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
        except (httpx.RequestError, requests.RequestException) as exc:
            error_message = f"Request error occurred: {exc}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
        except ValueError as exc:
            error_message = f"Invalid response format: {exc}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
