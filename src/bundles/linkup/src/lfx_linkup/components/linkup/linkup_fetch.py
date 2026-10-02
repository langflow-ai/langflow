from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import BoolInput, MessageTextInput, SecretStrInput
from lfx.schema.message import Message
from lfx.template.field.base import Output

from linkup import LinkupClient

# Rendering JavaScript loads the page in a headless browser, which can be slow.
REQUEST_TIMEOUT_SECONDS = 120.0


class LinkupFetchComponent(Component):
    """Component for fetching a web page as markdown with the Linkup API."""

    display_name = "Linkup Fetch"
    description = "Fetch a web page with Linkup and return its content as clean markdown."
    documentation = "https://docs.linkup.so/pages/documentation/api-reference/endpoint/post-fetch"
    icon = "Linkup"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="URL",
            required=True,
            info="The URL of the web page to fetch.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="linkup_api_key",
            display_name="Linkup API Key",
            required=True,
            info="Your Linkup API key. Get one at https://app.linkup.so.",
            password=True,
        ),
        BoolInput(
            name="render_js",
            display_name="Render JavaScript",
            value=False,
            info="Render the page in a browser before extracting content. Slower; use for pages built with "
            "client-side JavaScript.",
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode.
        Output(display_name="Markdown", name="markdown", method="linkup_fetch"),
    ]

    def _build_client(self) -> LinkupClient:
        if not self.linkup_api_key:
            msg = "Linkup API key is required. Set the Linkup API Key input."
            raise ValueError(msg)
        return LinkupClient(api_key=self.linkup_api_key)

    def linkup_fetch(self) -> Message:
        """Fetch the URL and return the page content as markdown."""
        url = (self.url or "").strip()
        if not url:
            msg = "URL is required."
            raise ValueError(msg)
        client = self._build_client()
        response = client.fetch(url, render_js=bool(self.render_js), timeout=REQUEST_TIMEOUT_SECONDS)
        message = Message(text=response.markdown)
        self.status = message
        return message
