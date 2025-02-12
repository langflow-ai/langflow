import httpx
from loguru import logger
from pathlib import Path
from langflow.components.agentql.utils import AGENTQL_QUERY_DOCUMENTATION, AGENTQL_REST_API_DOCUMENTATION, INVALID_API_KEY_MESSAGE
from langflow.base.data import BaseFileComponent
from langflow.io import (
    DictInput,
    IntInput,
    MultilineInput,
    SecretStrInput,
)
from langflow.schema import Data


class AgentQLQueryDoc(BaseFileComponent):
    display_name = "AgentQL Query Doc"
    description = "Uses AgentQL API to extract structured data from a given document."
    documentation: str = "https://docs.agentql.com/rest-api/api-reference"
    icon = "AgentQL"
    name = "AgentQL Query Doc"

    VALID_EXTENSIONS = ["jpeg", "png", "pdf", "jpg"]

    SUPPORTED_BUNDLE_EXTENSIONS = []

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="AgentQL API Key",
            required=True,
            password=True,
            info="Your AgentQL API key. Get one at https://dev.agentql.com.",
        ),
        *BaseFileComponent._base_inputs,
        MultilineInput(
            name="query",
            display_name="AgentQL Query",
            required=True,
            info=(f"The AgentQL query to execute. Read more at {AGENTQL_QUERY_DOCUMENTATION}."),
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
            info="The additional params to send with the request. Only 'mode' is supported. For details refer to https://docs.agentql.com/rest-api/api-reference#request-body.",
            is_list=True,
            value={
                "mode": "fast",
            },
            advanced=True,
        ),
    ]

    outputs = [
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        endpoint = "https://api.agentql.com/v1/query-document"
        headers = {
            "X-API-Key": self.api_key,
            "X-TF-Request-Origin": "langflow",
        }

        if len(file_list) > 1:
            self.status = "Only one file is supported for AgentQL Query Doc."
            raise ValueError(self.status)

        logger.info(f"Processing file: {file_list[0].path}")

        file = file_list[0]

        if not str(file.path).endswith(tuple(self.VALID_EXTENSIONS)):
            self.status = f"File extension {file.path} is not supported."
            raise ValueError(self.status)
        
        data = {
            "query": self.query,
        }

        path = Path(file.path)

        with path.open("rb") as f:
            files = {"file": f}

            try:
                response = httpx.post(endpoint, data=data, headers=headers, files=files, timeout=self.timeout)
                response.raise_for_status()

                json = response.json()
                data = Data(result=json["data"], metadata=json["metadata"])

            except httpx.HTTPStatusError as e:
                response = e.response
                if response.status_code in {401, 403}:
                    self.status = INVALID_API_KEY_MESSAGE
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
                file.data = data
                return [file]