import httpx
from loguru import logger

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data


class AgentQL(Component):
    display_name = "Extract Web Data"
    description = "Extracts structured data from a web page using an AgentQL query or a Natural Language description."
    documentation: str = "https://docs.agentql.com/rest-api/api-reference"
    icon = "AgentQL"
    name = "AgentQL"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            password=True,
            info="Your AgentQL API key from dev.agentql.com",
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            required=True,
            info="The URL of the public web page you want to extract data from.",
            tool_mode=True,
        ),
        MultilineInput(
            name="query",
            display_name="AgentQL Query",
            required=False,
            info="The AgentQL query to execute. Learn more at https://docs.agentql.com/agentql-query or use a prompt.",
            tool_mode=True,
        ),
        MultilineInput(
            name="prompt",
            display_name="Prompt",
            required=False,
            info="A Natural Language description of the data to extract from the page. Alternative to AgentQL query.",
            tool_mode=True,
        ),
        BoolInput(
            name="is_stealth_mode_enabled",
            display_name="Enable Stealth Mode (Beta)",
            info="Enable experimental anti-bot evasion strategies. May not work for all websites at all times.",
            value=False,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Seconds to wait for a request.",
            value=900,
            advanced=True,
        ),
        DropdownInput(
            name="mode",
            display_name="Request Mode",
            info="'standard' uses deep data analysis, while 'fast' trades some depth of analysis for speed.",
            options=["fast", "standard"],
            value="fast",
            advanced=True,
        ),
        IntInput(
            name="wait_for",
            display_name="Wait For",
            info="Seconds to wait for the page to load before extracting data.",
            value=0,
            range_spec=RangeSpec(min=0, max=10, step_type="int"),
            advanced=True,
        ),
        BoolInput(
            name="is_scroll_to_bottom_enabled",
            display_name="Enable scroll to bottom",
            info="Scroll to bottom of the page before extracting data.",
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="is_screenshot_enabled",
            display_name="Enable screenshot",
            info="Take a screenshot before extracting data. Returned in 'metadata' as a Base64 string.",
            value=False,
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
            "X-TF-Request-Origin": "langflow",
        }

        payload = {
            "url": self.url,
            "query": self.query,
            "prompt": self.prompt,
            "params": {
                "mode": self.mode,
                "wait_for": self.wait_for,
                "is_scroll_to_bottom_enabled": self.is_scroll_to_bottom_enabled,
                "is_screenshot_enabled": self.is_screenshot_enabled,
            },
            "metadata": {
                "experimental_stealth_mode_enabled": self.is_stealth_mode_enabled,
            },
        }

        if not self.prompt and not self.query:
            self.status = "Either Query or Prompt must be provided."
            raise ValueError(self.status)
        if self.prompt and self.query:
            self.status = "Both Query and Prompt can't be provided at the same time."
            raise ValueError(self.status)

        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()

            json = response.json()
            data = Data(result=json["data"], metadata=json["metadata"])

        except httpx.HTTPStatusError as e:
            response = e.response
            if response.status_code == httpx.codes.UNAUTHORIZED:
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
