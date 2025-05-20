import json
from pathlib import Path

import httpx
from loguru import logger

from langflow.base.data import BaseFileComponent
from langflow.components.agentql.utils import (
    AGENTQL_QUERY_DOCUMENTATION,
    AGENTQL_REST_API_DOCUMENTATION,
    INVALID_API_KEY_MESSAGE,
)
from langflow.io import (
    DropdownInput,
    IntInput,
    MultilineInput,
    SecretStrInput,
)
from langflow.schema import Data


class AgentQLQueryDocument(BaseFileComponent):
    display_name = "Extract Document Data"
    description = "Extracts structured data from a document using an AgentQL query or a Natural Language description."
    documentation: str = AGENTQL_REST_API_DOCUMENTATION
    icon = "AgentQL"
    name = "AgentQL Query Document"

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
            required=False,
            info=f"The AgentQL query to execute. Read more at {AGENTQL_QUERY_DOCUMENTATION}.",
            tool_mode=True,
        ),
        MultilineInput(
            name="prompt",
            display_name="Prompt",
            required=False,
            info="A Natural Language description of the data to extract from the page. Alternative to AgentQL query.",
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout in seconds for the request. Increase if data extraction takes too long.",
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
    ]

    outputs = [*BaseFileComponent._base_outputs]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        endpoint = "https://api.agentql.com/v1/query-document-body"
        headers = {
            "X-API-Key": self.api_key,
            "X-TF-Request-Origin": "langflow",
        }

        if len(file_list) > 1:
            self.status = "Only one file is supported for AgentQL Query Document."
            raise ValueError(self.status)

        logger.info(f"Processing file: {file_list[0].path}")

        file = file_list[0]

        if not str(file.path).endswith(tuple(self.VALID_EXTENSIONS)):
            self.status = f"File extension {file.path} is not supported."
            raise ValueError(self.status)

        form_data = {
            "query": self.query,
            "prompt": self.prompt,
            "params": {
                "mode": self.mode,
            },
        }

        if not self.prompt and not self.query:
            self.status = "Either Query or Prompt must be provided."
            raise ValueError(self.status)
        if self.prompt and self.query:
            self.status = "Both Query and Prompt can't be provided at the same time."
            raise ValueError(self.status)

        form_body = {"body": json.dumps(form_data)}

        path = Path(file.path)

        with path.open("rb") as f:
            files = {"file": (path.name, f)}

            try:
                response = httpx.post(endpoint, files=files, data=form_body, headers=headers, timeout=self.timeout)
                response.raise_for_status()

                response_json = response.json()
                data = Data(result=response_json["data"], metadata=response_json["metadata"])

            except httpx.HTTPStatusError as e:
                response = e.response
                if response.status_code in {401, 403}:
                    self.status = INVALID_API_KEY_MESSAGE
                else:
                    try:
                        error_json = response.json()
                        logger.error(
                            f"Failure response: '{response.status_code} {response.reason_phrase}' "
                            f"with body: {error_json}"
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
