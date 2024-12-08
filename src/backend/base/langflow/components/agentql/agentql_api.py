import httpx

from langflow.custom import Component
from langflow.io import DictInput, MultilineInput, Output, SecretStrInput, StrInput
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
            info="The AgentQL API key. Create at https://dev.agentql.com/",
        ),
        StrInput(
            name="url",
            display_name="URL",
            required=True,
            info="The URL of the webpage to query.",
        ),
        MultilineInput(
            name="query",
            display_name="Query",
            required=True,
            info="The AgentQL query to execute.",
        ),
        DictInput(
            name="params",
            display_name="Request Params",
            info="The request params to send with the request.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="build_output"),
    ]

    def build_output(self) -> Data:
        params = self.params.__dict__["data"] if self.params else {}

        url = "https://api.agentql.com/v1/query-data"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "query": self.query,
            "url": self.url,
            "params": params,
        }

        response = httpx.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = Data(data=response.json())
        self.status = data
        return data
