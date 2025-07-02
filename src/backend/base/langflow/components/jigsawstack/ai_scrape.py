from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output, SecretStrInput
from langflow.schema.data import Data

MAX_ELEMENT_PROMPTS = 5


class JigsawStackAIScraperComponent(Component):
    display_name = "AI Scraper"
    description = "Scrape any website instantly and get consistent structured data \
        in seconds without writing any css selector code"
    documentation = "https://jigsawstack.com/docs/api-reference/ai/scrape"
    icon = "JigsawStack"
    name = "JigsawStackAIScraper"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="JigsawStack API Key",
            info="Your JigsawStack API key for authentication",
            required=True,
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            info="URL of the page to scrape. Either url or html is required, but not both.",
            required=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="html",
            display_name="HTML",
            info="HTML content to scrape. Either url or html is required, but not both.",
            required=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="element_prompts",
            display_name="Element Prompts",
            info="Items on the page to be scraped (maximum 5). E.g. 'Plan price', 'Plan title'",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="root_element_selector",
            display_name="Root Element Selector",
            info="CSS selector to limit the scope of scraping to a specific element and its children",
            required=False,
            value="main",
        ),
    ]

    outputs = [
        Output(display_name="AI Scraper Results", name="scrape_results", method="scrape"),
    ]

    def scrape(self) -> Data:
        try:
            from jigsawstack import JigsawStack, JigsawStackError
        except ImportError as e:
            jigsawstack_import_error = (
                "JigsawStack package not found. Please install it using: pip install jigsawstack>=0.2.7"
            )
            raise ImportError(jigsawstack_import_error) from e

        try:
            client = JigsawStack(api_key=self.api_key)

            # Build request object
            scrape_params: dict = {}
            if self.url:
                scrape_params["url"] = self.url
            if self.html:
                scrape_params["html"] = self.html

            if len(scrape_params.get("url", "").strip()) == 0 and len(scrape_params.get("html", "").strip()) == 0:
                url_or_html_error = "Either 'url' or 'html' must be provided for scraping"
                raise ValueError(url_or_html_error)

            # Process element_prompts with proper type handling
            element_prompts_list: list[str] = []
            if self.element_prompts:
                element_prompts_value: str | list[str] = self.element_prompts

                if isinstance(element_prompts_value, str):
                    if "," not in element_prompts_value:
                        element_prompts_list = [element_prompts_value]
                    else:
                        element_prompts_list = element_prompts_value.split(",")
                elif isinstance(element_prompts_value, list):
                    element_prompts_list = element_prompts_value
                else:
                    # Fallback for other types
                    element_prompts_list = str(element_prompts_value).split(",")

                if len(element_prompts_list) > MAX_ELEMENT_PROMPTS:
                    max_elements_error = "Maximum of 5 element prompts allowed"
                    raise ValueError(max_elements_error)
                if len(element_prompts_list) == 0:
                    invalid_elements_error = "Element prompts cannot be empty"
                    raise ValueError(invalid_elements_error)

                scrape_params["element_prompts"] = element_prompts_list

            if self.root_element_selector:
                scrape_params["root_element_selector"] = self.root_element_selector

            # Call web scraping
            response = client.web.ai_scrape(scrape_params)

            if not response.get("success", False):
                fail_error = "JigsawStack API request failed."
                raise ValueError(fail_error)

            result_data = response

            self.status = "AI scrape process is now complete."

            return Data(data=result_data)

        except JigsawStackError as e:
            error_data = {"error": str(e), "success": False}
            self.status = f"Error: {e!s}"
            return Data(data=error_data)
