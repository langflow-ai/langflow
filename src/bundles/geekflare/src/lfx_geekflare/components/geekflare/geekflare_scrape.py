from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output

from ._api import GeekflareAPIError, call_api, normalize_url

FORMATS = ["markdown", "markdown-llm", "text", "text-llm", "html", "html-llm"]
TEMPLATES = ["none", "product", "contact"]


class GeekflareScrapeComponent(Component):
    """Scrape a public web page into Markdown, text, HTML, or structured JSON with Geekflare."""

    display_name = "Geekflare Scrape"
    description = "Fetch a public web page with Geekflare and return its content as Markdown, text, or HTML."
    documentation = "https://docs.geekflare.com/endpoint/webscraping"
    icon = "globe"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="URL",
            required=True,
            info="Full URL of the public page to scrape, or a domain such as example.com.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="geekflare_api_key",
            display_name="Geekflare API Key",
            required=True,
            info="Your Geekflare API key. Get one at https://dash.geekflare.com.",
            password=True,
        ),
        DropdownInput(
            name="output_format",
            display_name="Format",
            options=FORMATS,
            value="markdown",
            advanced=True,
            info="Output format. The -llm variants strip boilerplate.",
        ),
        DropdownInput(
            name="template",
            display_name="Template",
            options=TEMPLATES,
            value="none",
            advanced=True,
            info="Structured extraction: product (price, availability, ratings) or contact (emails, phones, socials).",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="geekflare_scrape"),
    ]

    def _request_body(self) -> dict:
        body: dict = {"url": normalize_url(self.url), "format": [self.output_format or "markdown"]}
        if self.template and self.template != "none":
            body["template"] = self.template
            body["extractionMode"] = "template"
        return body

    def geekflare_scrape(self) -> Data:
        """Scrape the page and return its content as Data."""
        try:
            payload = call_api(self.geekflare_api_key, "webscraping", self._request_body())
        except GeekflareAPIError as e:
            result = Data(text=str(e), data={"error": str(e)})
            self.status = result
            return result

        content = payload.get("data")
        if isinstance(content, dict):
            text = next(
                (content[key] for key in (self.output_format, "markdown", "text") if isinstance(content.get(key), str)),
                "",
            )
            result = Data(text=text, data={"url": normalize_url(self.url), **content})
        else:
            text = content if isinstance(content, str) else ""
            result = Data(text=text, data={"url": normalize_url(self.url), "content": content})
        self.status = result
        return result
