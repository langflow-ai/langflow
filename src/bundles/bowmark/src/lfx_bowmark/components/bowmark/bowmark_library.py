import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, SecretStrInput
from lfx.schema.message import Message
from lfx.template.field.base import Output

from . import _client

LIBRARY_ENDPOINT = f"{_client.API_BASE}/v1/library"


class BowmarkLibraryComponent(Component):
    """Look up which Bowmark functions exist for a website or task."""

    display_name = "Bowmark Library"
    description = (
        "Look up which functions Bowmark has for a website or task (for example 'linkedin.com' "
        "or 'flight prices'). Returns their names, arguments and return types."
    )
    documentation = "https://bowmark.ai"
    icon = "globe"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Query",
            required=True,
            info="A website hostname or a task, for example 'news.ycombinator.com' or 'track a parcel'.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="bowmark_api_key",
            display_name="Bowmark API Key",
            required=True,
            info="Your Bowmark API key. Get one at https://bowmark.ai.",
            password=True,
        ),
    ]

    outputs = [
        # The method name is also the tool name in tool mode; keep it specific.
        Output(display_name="Library", name="library", method="bowmark_get_library"),
    ]

    def _fetch(self) -> str:
        api_key = _client.require_key(self.bowmark_api_key)
        response = httpx.get(
            LIBRARY_ENDPOINT,
            params={"query": self.query or ""},
            headers=_client.headers(api_key),
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    def bowmark_get_library(self) -> Message:
        """Return the matching Bowmark functions as text an agent can read."""
        try:
            text = self._fetch()
        except httpx.HTTPStatusError as e:
            text = _client.http_error_message(e)
        except (httpx.HTTPError, ValueError) as e:
            text = str(e)
        self.status = text
        return Message(text=text)
