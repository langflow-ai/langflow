from loguru import logger

from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DataInput,
    IntInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data


class FirecrawlExtractApi(Component):
    display_name: str = "FirecrawlExtractApi"
    description: str = "Firecrawl Extract API for structured data extraction from websites."
    name = "FirecrawlExtractApi"

    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/extract"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            password=True,
            info="The API key to use Firecrawl API.",
        ),
        MultilineInput(
            name="urls",
            display_name="URLs",
            required=True,
            info="List of URLs to extract data from (separated by commas or new lines).",
            tool_mode=True,
        ),
        MultilineInput(
            name="prompt",
            display_name="Prompt",
            required=True,
            info="Prompt to guide the extraction process.",
            tool_mode=True,
        ),
        DataInput(
            name="schema",
            display_name="Schema",
            required=False,
            info="Schema to define the structure of the extracted data.",
            advanced=True,
        ),
        BoolInput(
            name="enable_web_search",
            display_name="Enable Web Search",
            info="When true, the extraction will use web search to find additional data.",
            default=False,
            advanced=True,
        ),
        BoolInput(
            name="ignoreSitemap",
            display_name="Ignore Sitemap",
            info="Skip sitemap.xml discovery for URL extraction.",
            default=False,
            advanced=True,
        ),
        BoolInput(
            name="includeSubdomains",
            display_name="Include Subdomains",
            info="Include URLs from subdomains in extraction.",
            default=True,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout in seconds for the extraction process.",
            default=300,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="extract"),
    ]
    
    enable_web_search: bool = False
    ignoreSitemap: bool = False
    includeSubdomains: bool = True
    timeout: int = 300

    def extract(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        # Validate API key
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)

        # Strip whitespace from API key
        cleaned_api_key = self.api_key.strip() if self.api_key else ""

        # Validate URLs
        if not self.urls:
            msg = "URLs are required"
            raise ValueError(msg)

        # Split and validate URLs (handle both commas and newlines)
        urls = [url.strip() for url in self.urls.replace("\n", ",").split(",") if url.strip()]
        if not urls:
            msg = "No valid URLs provided"
            raise ValueError(msg)

        # Validate and process prompt
        if not self.prompt:
            msg = "Prompt is required"
            raise ValueError(msg)

        # Get the prompt text
        prompt_text = self.prompt.strip()

        # Enhance the prompt to encourage comprehensive extraction
        enhanced_prompt = prompt_text
        if "schema" not in prompt_text.lower():
            enhanced_prompt = f"{prompt_text}. Please extract all instances in a comprehensive, structured format."

        # Build parameters for API request
        params = {
            "prompt": enhanced_prompt,
            "enableWebSearch": self.enable_web_search,
            "ignoreSitemap": self.ignoreSitemap,
            "includeSubdomains": self.includeSubdomains,
            "timeout": self.timeout,
        }

        # Only add schema to params if it's provided and is a valid schema structure
        if self.schema:
            try:
                if isinstance(self.schema, dict) and "type" in self.schema:
                    params["schema"] = self.schema
                elif hasattr(self.schema, "__dict__") and hasattr(self.schema.__dict__, "data"):
                    params["schema"] = self.schema.__dict__["data"]
                else:
                    logger.warning("Schema provided but format is not recognized. Skipping schema.")
            except Exception as e:
                logger.warning(f"Invalid schema format: {e!s}. Proceeding without schema.")

        try:
            # Create Firecrawl client and extract data
            app = FirecrawlApp(api_key=cleaned_api_key)
            extract_result = app.extract(urls, params=params)
            return Data(data=extract_result)
        except Exception as e:
            error_message = str(e)
            if "401" in error_message:
                msg = f"Authentication failed: Please check your Firecrawl API key. Error: {error_message}"
            elif "403" in error_message:
                msg = f"Authorization failed: Your API key may not have permission to use this feature. Error: {error_message}"
            else:
                msg = f"Error during extraction: {error_message}"
            logger.error(msg)
            raise ValueError(msg) from e