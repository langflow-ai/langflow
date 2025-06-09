#brightdata_web_scraper.py
from langflow.custom import Component
from langflow.inputs import SecretStrInput, StrInput, DropdownInput, IntInput
from langflow.template import Output
from langflow.schema import Data
from typing import List
import requests
import json


class BrightDataWebScraperComponent(Component):
    display_name = "Bright Data Web Scraper"
    description = "Scrape web content using Bright Data's web scraping service with bot detection bypass"
    icon = "globe"
    name = "BrightDataWebScraper"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="API Token",
            info="Your Bright Data API token",
            required=True,
        ),
        StrInput(
            name="url",
            display_name="URL",
            info="The URL to scrape",
            required=True,
        ),
        DropdownInput(
            name="output_format",
            display_name="Output Format",
            options=["markdown", "html"],
            value="markdown",
            info="Choose the output format for the scraped content",
        ),
        StrInput(
            name="zone_name",
            display_name="Zone Name",
            value="mcp_unlocker",
            info="Bright Data zone name (defaults to mcp_unlocker)",
        ),
    ]

    outputs = [
        Output(display_name="Scraped Content", name="content", method="scrape_content"),
    ]

    def scrape_content(self) -> Data:
        """Scrape content from the specified URL using Bright Data"""
        try:
            headers = {
                'authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json',
            }
            
            payload = {
                'url': self.url,
                'zone': self.zone_name,
                'format': 'raw',
            }
            
            if self.output_format == "markdown":
                payload['data_format'] = 'markdown'
            
            response = requests.post(
                'https://api.brightdata.com/request',
                json=payload,
                headers=headers,
                timeout=120
            )
            
            if response.status_code == 200:
                content = response.text
                return Data(
                    text=content,
                    data={
                        "url": self.url,
                        "format": self.output_format,
                        "status": "success",
                        "content_length": len(content)
                    }
                )
            else:
                error_msg = f"Error scraping URL: HTTP {response.status_code} - {response.text}"
                return Data(
                    text=error_msg,
                    data={
                        "url": self.url,
                        "status": "error",
                        "error": error_msg
                    }
                )
                
        except Exception as e:
            error_msg = f"Exception occurred while scraping: {str(e)}"
            return Data(
                text=error_msg,
                data={
                    "url": self.url,
                    "status": "error",
                    "error": error_msg
                }
            )