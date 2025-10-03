import json

from lfx.base.io.text import TextComponent
from lfx.io import MultilineInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message


class JSONInputComponent(TextComponent):
    display_name = "JSON Input"
    description = "Receives and destructures an HTTP request JSON payload."
    icon = "braces"
    name = "JSONInput"

    inputs = [
        MultilineInput(
            name="payload",
            display_name="Payload",
            info="Manual JSON payload for testing (will be overridden by actual HTTP request when used via API)",
            value=(
                '{\n  "method": "POST",\n  "headers": {"Content-Type": "application/json"},'
                '\n  "body": {"name": "test", "value": 123},\n  "query": {"page": "1"},'
                '\n  "path": {"id": "456"},\n  "url": "/api/test/456"\n}'
            ),
            advanced=False,
        ),
    ]

    outputs = [
        Output(display_name="Method", name="method", method="get_method"),
        Output(display_name="Headers", name="headers", method="get_headers"),
        Output(display_name="Body", name="body", method="get_body"),
        Output(display_name="Query Params", name="query", method="get_query"),
        Output(display_name="Path Params", name="path", method="get_path"),
        Output(display_name="URL", name="url", method="get_url"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # These will be populated by the API endpoint
        self.request_data = None

    def set_request_data(self, request_data: dict):
        """Called by the API endpoint to inject request data."""
        self.request_data = request_data

    def _get_payload_data(self) -> dict:
        """Get payload data from either API injection or manual input."""
        if self.request_data is not None:
            # Use injected data from API endpoint
            return self.request_data

        try:
            # Parse manual payload input for testing
            payload_text = getattr(self, "payload", "{}")
            return json.loads(payload_text)
        except (json.JSONDecodeError, AttributeError):
            # Fallback to default values
            return {"method": "GET", "headers": {}, "body": {}, "query": {}, "path": {}, "url": "/"}

    def get_method(self) -> Message:
        """Returns the HTTP method as a Message."""
        data = self._get_payload_data()
        return Message(text=data.get("method", "GET"))

    def get_headers(self) -> Data:
        """Returns request headers as Data."""
        data = self._get_payload_data()
        headers = data.get("headers", {})
        return Data(data=headers)

    def get_body(self) -> Data:
        """Returns request body as Data."""
        data = self._get_payload_data()
        body = data.get("body", {})
        return Data(data=body)

    def get_query(self) -> Data:
        """Returns query parameters as Data."""
        data = self._get_payload_data()
        query = data.get("query", {})
        return Data(data=query)

    def get_path(self) -> Data:
        """Returns path parameters as Data."""
        data = self._get_payload_data()
        path = data.get("path", {})
        return Data(data=path)

    def get_url(self) -> Message:
        """Returns the request URL as a Message."""
        data = self._get_payload_data()
        url = data.get("url", "/")
        return Message(text=url)
