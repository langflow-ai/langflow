# brightdata_web_scraper.py
from langflow.custom import Component
from langflow.inputs import SecretStrInput, StrInput, DropdownInput, MessageTextInput
from langflow.template import Output
from langflow.schema import Data
import requests


class BrightDataWebScraperComponent(Component):
    display_name = "Bright Data Web Scraper"
    description = "Scrape the web with bot detection bypass and unlocking tools powered by Bright Data"
    icon = "BrightData"
    name = "BrightDataWebScraper"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="🔑 API Key",
            info="Insert Your Bright Data API Key Here",
            placeholder="Enter your Bright Data API token...",
            required=True,
        ),
        MessageTextInput(
            name="url_input",
            display_name="🔍 URL Input",
            info="The URL to scrape - can be connected from another component or entered manually",
            required=True,
            tool_mode=True,
            placeholder="https://example.com/page",
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
            advanced=True,
        ),
        DropdownInput(
            name="timeout",
            display_name="Timeout (seconds)",
            options=["60", "120", "180", "300"],
            value="120",
            info="Request timeout in seconds",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Scraped Content", name="content", method="scrape_content"),
        Output(display_name="URL Used", name="url", method="get_url"),
        Output(display_name="Metadata", name="metadata", method="get_metadata"),
    ]

    def get_url_from_input(self) -> str:
        """Extract URL from the input, handling both Message and string types"""
        # Langflow automatically converts inputs to appropriate types
        # We just need to handle Message vs string cases
        if hasattr(self.url_input, 'text'):
            # It's a Message object
            return str(self.url_input.text).strip()
        else:
            # It's already a string or can be converted to string
            return str(self.url_input or "").strip()

    def scrape_content(self) -> Data:
        """Scrape content from the specified URL using Bright Data"""
        try:
            url = self.get_url_from_input()
            
            if not url:
                error_msg = "No URL provided"
                return Data(
                    text=error_msg,
                    data={
                        "status": "error",
                        "error": error_msg
                    }
                )
            
            # Validate URL format
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            headers = {
                'authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'Langflow-BrightData-Component/1.0'
            }
            
            payload = {
                'url': url,
                'zone': self.zone_name,
                'format': 'raw',
            }
            
            if self.output_format == "markdown":
                payload['data_format'] = 'markdown'
            
            timeout = int(self.timeout)
            
            response = requests.post(
                'https://api.brightdata.com/request',
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            if response.status_code == 200:
                content = response.text
                
                # Store metadata for other outputs
                self._scraped_url = url
                self._metadata = {
                    "url": url,
                    "format": self.output_format,
                    "status": "success",
                    "content_length": len(content),
                    "zone": self.zone_name,
                    "response_headers": dict(response.headers),
                    "status_code": response.status_code
                }
                
                return Data(
                    text=content,
                    data=self._metadata
                )
            else:
                error_msg = f"Error scraping URL: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except Exception:
                    error_msg += f" - {response.text}"
                
                self._scraped_url = url
                self._metadata = {
                    "url": url,
                    "status": "error",
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
                return Data(
                    text=error_msg,
                    data=self._metadata
                )
                
        except requests.exceptions.Timeout:
            error_msg = f"Request timed out after {self.timeout} seconds"
            return self._create_error_data(url if 'url' in locals() else "unknown", error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error - please check your internet connection"
            return self._create_error_data(url if 'url' in locals() else "unknown", error_msg)
        except Exception as e:
            error_msg = f"Exception occurred while scraping: {str(e)}"
            return self._create_error_data(url if 'url' in locals() else "unknown", error_msg)

    def _create_error_data(self, url: str, error_msg: str) -> Data:
        """Helper method to create error data"""
        self._scraped_url = url
        self._metadata = {
            "url": url,
            "status": "error",
            "error": error_msg
        }
        return Data(
            text=error_msg,
            data=self._metadata
        )

    def get_url(self) -> Data:
        """Return the URL that was used for scraping"""
        url = getattr(self, '_scraped_url', self.get_url_from_input())
        return Data(text=url)

    def get_metadata(self) -> Data:
        """Return metadata about the scraping operation"""
        metadata = getattr(self, '_metadata', {
            "url": self.get_url_from_input(),
            "status": "not_executed"
        })
        return Data(data=metadata)