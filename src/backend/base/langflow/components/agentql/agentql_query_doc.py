import json

import httpx
from loguru import logger

from langflow.base.data import BaseFileComponent
from langflow.components.agentql.utils import (
    AGENTQL_QUERY_DOCUMENT_DOCUMENTATION,
    AGENTQL_QUERY_DOCUMENTATION,
    DOUBLE_INPUT_MESSAGE,
    NO_INPUT_MESSAGE,
    handle_agentql_error,
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
    documentation: str = AGENTQL_QUERY_DOCUMENT_DOCUMENTATION
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
            info="Your AgentQL API key from dev.agentql.com",
        ),
        *BaseFileComponent._base_inputs,
        MultilineInput(
            name="query",
            display_name="AgentQL Query",
            required=False,
            info=f"The AgentQL query to execute. Learn more at {AGENTQL_QUERY_DOCUMENTATION} or use a prompt.",
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
    ]

    outputs = [*BaseFileComponent._base_outputs]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        endpoint = "https://api.agentql.com/v1/query-document"
        headers = {
            "X-API-Key": self.api_key,
            "X-TF-Request-Origin": "langflow",
        }

        if len(file_list) > 1:
            self.status = "Only one file is supported for AgentQL Query Document."
            raise ValueError(self.status)

        logger.info(f"Processing file: {file_list[0].path}")

        file = file_list[0]

        form_data = {
            "query": self.query,
            "prompt": self.prompt,
            "params": {
                "mode": self.mode,
            },
        }

        if not self.prompt and not self.query:
            self.status = NO_INPUT_MESSAGE
            raise ValueError(self.status)
        if self.prompt and self.query:
            self.status = DOUBLE_INPUT_MESSAGE
            raise ValueError(self.status)

        path = file.path
        with path.open("rb") as f:
            files = {"file": (path.name, f)}
            form_body = {"body": json.dumps(form_data)}

            try:
                response = httpx.post(endpoint, files=files, data=form_body, headers=headers, timeout=self.timeout)
                response.raise_for_status()

                response_json = response.json()
                data = Data(result=response_json["data"], metadata=response_json["metadata"])

            except httpx.HTTPStatusError as e:
                self.status = handle_agentql_error(e)
                raise ValueError(self.status) from e
            self.status = data
            file.data = data
            return [file]
