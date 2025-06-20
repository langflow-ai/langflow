from typing import Any

from langflow.custom.custom_component.component import Component
from langflow.io import MessageTextInput, Output, SecretStrInput, DataInput, StrInput, CodeInput
from langflow.schema.data import Data
from langflow.schema.message import Message


class JigsawStackAIScraperComponent(Component):
    display_name = "AI Scraper"
    description = "Scrape any website instantly and get consistent structured data in seconds without writing any css selector code"
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
            info="Comma Seperated Items on the page to be scraped (maximum 5). E.g. “Plan price”, “Plan title”",
            required=True,
            is_list=True
        ),
        StrInput(
            name="root_element_selector",
            display_name="Spell Check",
            info="Spell check the search query",
            required=False,
            value="main",
        )
    ]

    outputs = [
        Output(display_name="AI Scraper Results", name="scrape_results", method="scrape"),
    ]

    def scrape(self) -> Data:
        try:
            from jigsawstack import JigsawStack
        except ImportError as e:
            raise ImportError(
                "JigsawStack package not found"
            ) from e

        try:
            client = JigsawStack(api_key=self.api_key)
            
            #build request object
            scrape_params = {}
            if self.url:
                scrape_params["url"] = self.url
            if self.html:
                scrape_params["html"] = self.html

            if len(scrape_params["url"].strip(" ")) == 0 and len(scrape_params["html"].strip()) == 0:
                raise ValueError("Either 'url' or 'html' must be provided for scraping")
            
            if self.element_prompts:
                if isinstance(self.element_prompts, str):
                    if "," not in self.element_prompts:
                        self.element_prompts = [self.element_prompts]
                    else:
                        self.element_prompts = self.element_prompts.split(",")
                elif not isinstance(self.element_prompts, list):
                    self.element_prompts = self.element_prompts.split(",")
                
                if len(self.element_prompts) > 5:
                    raise ValueError("Maximum of 5 element prompts allowed")
                elif len(self.element_prompts) == 0:
                    raise ValueError("At least one element prompt must be provided")
                
                scrape_params["element_prompts"] = self.element_prompts
            if self.root_element_selector:
                scrape_params["root_element_selector"] = self.root_element_selector
            
            # Call web scraping
            response = client.web.ai_scrape(scrape_params)
            
            if not response.get("success", False):
                raise ValueError("JigsawStack API returned unsuccessful response")

            result_data = response 
            
            self.status = f"AI scrape process is now complete."
            
            return Data(data=result_data)
            
        except Exception as e:
            error_data = {
                "error": str(e),
                "success": False
            }
            self.status = f"Error: {str(e)}"
            return Data(data=error_data)