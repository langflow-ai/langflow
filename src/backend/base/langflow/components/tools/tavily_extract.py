import httpx
from loguru import logger

from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput
from langflow.schema import Data
from langflow.schema.message import Message


class TavilyExtractComponent(Component):
    """Separate component specifically for Tavily Extract functionality"""

    display_name = "Tavily Extract API"
    description = """**Tavily Extract** extract raw content from URLs."""
    icon = "TavilyIcon"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Tavily API Key",
            required=True,
            info="Your Tavily API Key.",
        ),
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="Comma-separated list of URLs to extract content from.",
            required=True,
        ),
        DropdownInput(
            name="extract_depth",
            display_name="Extract Depth",
            info="The depth of the extraction process.",
            options=["basic", "advanced"],
            value="basic",
            advanced=True,
        ),
        BoolInput(
            name="include_images",
            display_name="Include Images",
            info="Include a list of images extracted from the URLs.",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
        Output(display_name="Text", name="text", method="fetch_content_text"),
    ]

    def fetch_content(self) -> list[Data]:
        """Fetches and processes extracted content into a list of Data objects."""
        try:
            # Split URLs by comma and clean them
            urls = [url.strip() for url in (self.urls or "").split(",") if url.strip()]
            if not urls:
                error_message = "No valid URLs provided"
                logger.error(error_message)
                # Return list with a single error Data object
                return [Data(text=error_message, data={"error": error_message})]

            url = "https://api.tavily.com/extract"
            headers = {
                "content-type": "application/json",
                "accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = {
                "urls": urls,
                "extract_depth": self.extract_depth,
                "include_images": self.include_images,
            }

            # Add timeout handling
            with httpx.Client(timeout=90.0) as client:
                response = client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            extract_results = response.json()

            data_results = [] # Initialize list to hold Data objects

            # Process successful extractions
            for result in extract_results.get("results", []):
                raw_content = result.get("raw_content", "")
                images = result.get("images", [])
                # Create structured data with only url and content (as raw_content)
                result_data = {
                    "url": result.get("url"),
                    "raw_content": raw_content,     
                    "images": images
                }
                # The 'text' field of Data still holds the main content for compatibility
                data_results.append(Data(text=raw_content, data=result_data))

            # Process failed extractions
            if extract_results.get("failed_results"):
                # Append a separate Data object for failures
                data_results.append(
                    Data(
                        text="Failed extractions",
                        data={"failed_results": extract_results["failed_results"]},
                    )
                )

            self.status = data_results # Set status to the list of Data objects
            return data_results # Return the list

        # Updated error handling to return list[Data]
        except httpx.TimeoutException as exc:
            error_message = "Request timed out (90s). Please try again or reduce the number of URLs."
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
        except Exception as exc:
             error_message = f"An unexpected error occurred: {exc}"
             logger.error(error_message)
             return [Data(text=error_message, data={"error": error_message})]

    def fetch_content_text(self) -> Message:
        # This method should still work as it expects a list from fetch_content
        data = self.fetch_content()
        result_string = data_to_text("{text}", data)
        self.status = result_string
        return Message(text=result_string) 