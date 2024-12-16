import httpx
from loguru import logger

from langflow.custom import Component
from langflow.io import (
    DictInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data


class AgentQL(Component):
    display_name = "AgentQL Query Data"
    description = "Uses AgentQL API to extract structured data from a given URL."
    documentation: str = "https://docs.agentql.com/rest-api/api-reference"
    icon = "AgentQL"
    name = "AgentQL"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="AgentQL API Key",
            required=True,
            password=True,
            info="Your AgentQL API key. Get one at https://dev.agentql.com.",
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            required=True,
            info="The public URL of the webpage to extract data from.",
            tool_mode=True,
        ),
        MultilineInput(
            name="query",
            display_name="AgentQL Query",
            required=True,
            info="The AgentQL query to execute. Read more at https://docs.agentql.com/agentql-query.",
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout in seconds for the request. Increase if data extraction takes too long.",
            value=900,
            advanced=True,
        ),
        DictInput(
            name="params",
            display_name="Additional Params",
            info="The additional params to send with the request. For details refer to https://docs.agentql.com/rest-api/api-reference#request-body.",
            is_list=True,
            value={
                "mode": "fast",
                "wait_for": 0,
                "is_scroll_to_bottom_enabled": False,
                "is_screenshot_enabled": False,
            },
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="build_output"),
    ]

    def build_output(self) -> Data:
        endpoint = "https://api.agentql.com/v1/query-data"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "url": self.url,
            "query": self.query,
            "params": self.params,
        }

        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()

            json = response.json()
            data = Data(result=json["data"], metadata=json["metadata"])

        except httpx.HTTPStatusError as e:
            response = e.response
            if response.status_code in [401, 403]:
                self.status = "Please, provide a valid API Key. You can create one at https://dev.agentql.com."
            else:
                try:
                    error_json = response.json()
                    logger.error(
                        f"Failure response: '{response.status_code} {response.reason_phrase}' with body: {error_json}"
                    )
                    msg = error_json["error_info"] if "error_info" in error_json else error_json["detail"]
                except (ValueError, TypeError):
                    msg = f"HTTP {e}."
                self.status = msg
            raise ValueError(self.status) from e

        else:
            self.status = data
            return data
