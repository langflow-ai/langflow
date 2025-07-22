from loguru import logger

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DataInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from lfx.schema.data import Data


class FirecrawlExtractApi(Component):
    display_name: str = "FirecrawlExtractApi"
    description: str = "Firecrawl Extract API."
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
        ),
        BoolInput(
            name="enable_web_search",
            display_name="Enable Web Search",
            info="When true, the extraction will use web search to find additional data.",
        ),
        # # Optional: Not essential for basic extraction
        # BoolInput(
        #     name="ignore_sitemap",
        #     display_name="Ignore Sitemap",
        #     info="When true, sitemap.xml files will be ignored during website scanning.",
        # ),
        # # Optional: Not essential for basic extraction
        # BoolInput(
        #     name="include_subdomains",
        #     display_name="Include Subdomains",
        #     info="When true, subdomains of the provided URLs will also be scanned.",
        # ),
        # # Optional: Not essential for basic extraction
        # BoolInput(
        #     name="show_sources",
        #     display_name="Show Sources",
        #     info="When true, the sources used to extract the data will be included in the response.",
        # ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="extract"),
    ]

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

        # Get the prompt text (handling both string and multiline input)
        prompt_text = self.prompt.strip()

        # Enhance the prompt to encourage comprehensive extraction
        enhanced_prompt = prompt_text
        if "schema" not in prompt_text.lower():
            enhanced_prompt = f"{prompt_text}. Please extract all instances in a comprehensive, structured format."

        params = {
            "prompt": enhanced_prompt,
            "enableWebSearch": self.enable_web_search,
            # Optional parameters - not essential for basic extraction
            "ignoreSitemap": self.ignore_sitemap,
            "includeSubdomains": self.include_subdomains,
            "showSources": self.show_sources,
            "timeout": 300,
        }

        # Only add schema to params if it's provided and is a valid schema structure
        if self.schema:
            try:
                if isinstance(self.schema, dict) and "type" in self.schema:
                    params["schema"] = self.schema
                elif hasattr(self.schema, "dict") and "type" in self.schema.dict():
                    params["schema"] = self.schema.dict()
                else:
                    # Skip invalid schema without raising an error
                    pass
            except Exception as e:  # noqa: BLE001
                logger.error(f"Invalid schema: {e!s}")

        try:
            app = FirecrawlApp(api_key=self.api_key)
            extract_result = app.extract(urls, params=params)
            return Data(data=extract_result)
        except Exception as e:
            msg = f"Error during extraction: {e!s}"
            raise ValueError(msg) from e
