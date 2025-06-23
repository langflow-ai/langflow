import httpx
import json
from loguru import logger

from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.template.field.base import Output


class TavilyCrawlComponent(Component):
    display_name = "Tavily Crawl API"
    description = """**Tavily Crawl** intelligently crawl a website from a starting URL to discover and extract content across multiple pages."""
    icon = "TavilyIcon"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Tavily API Key",
            required=True,
            info="Your Tavily API Key.",
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            required=True,
            info="The root URL to begin the crawl.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            info="Natural language instructions for the crawler."
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            info="Max depth of the crawl. Defines how far from the base URL the crawler can explore.",
            value=1,
            advanced=True,
        ),
        IntInput(
            name="max_breadth",
            display_name="Max Breadth",
            info="Max number of links to follow per level of the tree (i.e., per page).",
            value=20,
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="Total number of links the crawler will process before stopping.",
            value=50,
            advanced=True,
        ),
        MessageTextInput(
            name="categories",
            display_name="Categories",
            info="Enter a JSON array of categories, e.g. [\"Careers\", \"Blog\", \"Documentation\"]. Available: Careers, Blog, Documentation, About, Pricing, Community, Developers, Contact, Media",
            advanced=True,
        ),
        MessageTextInput(
            name="select_paths",
            display_name="Select Paths",
            info="Regex patterns to select only URLs with specific path patterns (e.g., /docs/.*, /api/v1.*). Enter as a JSON array: [\"/docs/.*\", \"/api/v1.*\"]",
            advanced=True,
        ),
        MessageTextInput(
            name="select_domains",
            display_name="Select Domains",
            info="Regex patterns to select crawling to specific domains or subdomains (e.g., ^private\\.example\\.com$). Enter as a JSON array: [\"^private\\.example\\.com$\"]",
            advanced=True,
        ),
        MessageTextInput(
            name="exclude_paths",
            display_name="Exclude Paths",
            info="Regex patterns to exclude URLs with specific path patterns (e.g., /private/.*, /admin/.*). Enter as a JSON array: [\"/private/.*\", \"/admin/.*\"]",
            advanced=True,
        ),
        MessageTextInput(
            name="exclude_domains",
            display_name="Exclude Domains",
            info="Regex patterns to exclude specific domains or subdomains from crawling (e.g., ^private\\.example\\.com$). Enter as a JSON array: [\"^private\\.example\\.com$\"]",
            advanced=True,
        ),
        BoolInput(
            name="allow_external",
            display_name="Allow External",
            info="Whether to allow following links that go to external domains.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="include_images",
            display_name="Include Images",
            info="Whether to include images in the crawl results.",
            value=False,
            advanced=True,
        ),
        DropdownInput(
            name="extract_depth",
            display_name="Extract Depth",
            info="Advanced extraction retrieves more data, including tables and embedded content, with higher success but may increase latency.",
            options=["basic", "advanced"],
            value="basic",
            advanced=True,
        ),
        DropdownInput(
            name="format",
            display_name="Format",
            info="The format of the extracted web page content. markdown returns content in markdown format. text returns plain text and may increase latency.",
            options=["markdown", "text"],
            value="markdown",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="DataFrame", name="dataframe", method="fetch_content_dataframe"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            url = "https://api.tavily.com/crawl"
            headers = {
                "content-type": "application/json",
                "accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "X-Client-Source": "langflow"
            }

            payload = {
                "url": self.url,
                "max_depth": self.max_depth,
                "max_breadth": self.max_breadth,
                "limit": self.limit,
                "allow_external": self.allow_external,
                "include_images": self.include_images,
                "extract_depth": self.extract_depth,
                "format": self.format,
            }

            # Add optional parameters if they exist
            if hasattr(self, "instructions") and self.instructions:
                payload["instructions"] = self.instructions

            for param in ["select_paths", "select_domains", "exclude_paths", "exclude_domains", "categories"]:
                value = getattr(self, param, None)
                if value:
                    try:
                        value_list = json.loads(value)
                        if isinstance(value_list, list):
                            payload[param] = value_list
                        else:
                            payload[param] = [value]
                    except Exception:
                        payload[param] = [value]

            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            crawl_results = response.json()

            data_results = []

            # Process results based on the expected format
            results = crawl_results.get("results", [])
            response_time = crawl_results.get("response_time")
            
            for result in results:
                url = result.get("url", "")
                raw_content = result.get("raw_content", "")
                
                result_data = {
                    "url": url,
                    "raw_content": raw_content,
                }
                
                # Use raw_content as the text for the Data object
                data_results.append(Data(text=raw_content,data=result_data))

            # Add response time information to the last data point if available
            if data_results and response_time is not None:
                data_results[-1].data["response_time"] = response_time
            
            # If no results were found, return a message with the response time
            if not data_results:
                message = "No results found in crawl response"
                if response_time is not None:
                    message += f" (response time: {response_time}s)"
                data_results.append(Data(text=message, data={"response_time": response_time}))

        except httpx.TimeoutException:
            error_message = "Request timed out (120s). Please try again or adjust parameters."
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except httpx.HTTPStatusError as exc:
            error_message = f"HTTP error occurred: {exc.response.status_code} - {exc.response.text}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except httpx.RequestError as exc:
            error_message = f"Request error occurred: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        except ValueError as exc:
            error_message = f"Invalid response format: {exc}"
            logger.error(error_message)
            return [Data(text=error_message, data={"error": error_message})]
        else:
            self.status = data_results
            return data_results

    def fetch_content_dataframe(self) -> DataFrame:
        data = self.fetch_content()
        return DataFrame(data)
