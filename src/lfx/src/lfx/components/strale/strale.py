import json
from typing import Any

import httpx
from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel, Field

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import DropdownInput, MessageTextInput, MultilineInput, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

DEFAULT_BASE_URL = "https://api.strale.io"
REQUEST_TIMEOUT = 60.0


class SearchAndExecuteSchema(BaseModel):
    task: str = Field(
        ...,
        description=(
            "Natural language description of the data you need, "
            "e.g. 'verify a Swedish company' or 'validate this VAT number'"
        ),
    )
    inputs: str | None = Field(
        default=None,
        description='Optional JSON object with inputs for the matched capability, e.g. \'{"company_name": "Volvo"}\'',
    )


class ExecuteCapabilitySchema(BaseModel):
    inputs: str = Field(
        ...,
        description='JSON object with the inputs required by the capability, e.g. \'{"company_name": "Volvo"}\'',
    )


class StraleComponent(LCToolComponent):
    display_name = "Strale"
    description = (
        "Access Strale's data capability catalog — company verification, "
        "sanctions screening, VAT validation, web extraction, and more"
    )
    name = "Strale"
    icon = "Shield"
    documentation = "https://strale.dev"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Strale API Key",
            info=(
                "Your Strale API key. Optional — 5 free capabilities "
                "(email-validate, dns-lookup, json-repair, url-to-markdown, "
                "iban-validate) work without auth."
            ),
            required=False,
        ),
        DropdownInput(
            name="tool_mode",
            display_name="Mode",
            info=(
                "'Search and execute' finds the best capability for a task "
                "description. 'Execute a specific capability' calls a known "
                "capability slug directly."
            ),
            options=["Search and execute", "Execute a specific capability"],
            value="Search and execute",
        ),
        MessageTextInput(
            name="capability_slug",
            display_name="Capability Slug",
            info=(
                "The slug of the capability to execute "
                "(e.g. 'swedish-company-data'). Only used in 'Execute a "
                "specific capability' mode."
            ),
            advanced=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Input",
            info="Task description (search mode) or JSON inputs (execute mode).",
            tool_mode=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            info="Strale API base URL. Override for self-hosted or staging instances.",
            value=DEFAULT_BASE_URL,
            advanced=True,
        ),
    ]

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_base_url(self) -> str:
        return (self.base_url or DEFAULT_BASE_URL).rstrip("/")

    def _suggest(self, client: httpx.Client, task: str, limit: int = 3) -> list[dict[str, Any]]:
        """Call POST /v1/suggest to find matching capabilities."""
        response = client.post(
            f"{self._get_base_url()}/v1/suggest",
            json={"task": task, "limit": limit},
            headers=self._get_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return data.get("suggestions", data.get("capabilities", []))

    def _execute(
        self,
        client: httpx.Client,
        capability_slug: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Call POST /v1/do to execute a capability."""
        response = client.post(
            f"{self._get_base_url()}/v1/do",
            json={"capability_slug": capability_slug, "inputs": inputs},
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def _parse_inputs(self, raw: str | None) -> dict[str, Any]:
        """Parse a JSON string into a dict, or return an empty dict."""
        if not raw or not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Treat plain text as a single-key input
            return {"query": raw}
        if not isinstance(parsed, dict):
            return {"query": str(parsed)}
        return parsed

    def _search_and_execute(self, task: str, inputs: str | None = None) -> list[Data]:
        """Search for the best capability and execute it."""
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            suggestions = self._suggest(client, task)
            if not suggestions:
                error_data = Data(data={"error": "No matching capabilities found", "task": task})
                self.status = error_data
                return [error_data]

            best = suggestions[0]
            slug = best.get("slug") or best.get("capability_slug", "")

            parsed_inputs = self._parse_inputs(inputs)
            result = self._execute(client, slug, parsed_inputs)

        return self._format_result(result, slug)

    def _execute_specific(self, inputs_raw: str) -> list[Data]:
        """Execute a specific capability by slug."""
        slug = self.capability_slug
        if not slug:
            error_data = Data(data={"error": "capability_slug is required in 'Execute a specific capability' mode"})
            self.status = error_data
            return [error_data]

        parsed_inputs = self._parse_inputs(inputs_raw)

        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            result = self._execute(client, slug, parsed_inputs)

        return self._format_result(result, slug)

    def _format_result(self, result: dict[str, Any], slug: str) -> list[Data]:
        """Format an API response into Data objects."""
        output = result.get("output", result)
        quality = result.get("quality", {})
        transaction_id = result.get("transaction_id")
        wallet_balance = result.get("wallet_balance_cents")

        data = Data(
            data={
                "capability_slug": slug,
                "output": output,
                "quality": quality,
                "transaction_id": transaction_id,
                "wallet_balance_cents": wallet_balance,
            },
        )
        self.status = data
        return [data]

    def run_model(self) -> list[Data]:
        try:
            if self.tool_mode == "Execute a specific capability":
                return self._execute_specific(self.input_value)
            return self._search_and_execute(self.input_value)
        except httpx.TimeoutException as e:
            error_message = f"Request timed out ({REQUEST_TIMEOUT}s). Please try again."
            logger.error(f"Strale timeout: {e}")
            self.status = error_message
            raise ToolException(error_message) from e
        except httpx.HTTPStatusError as e:
            error_message = f"Strale API error: {e.response.status_code} - {e.response.text}"
            logger.debug(error_message)
            self.status = error_message
            raise ToolException(error_message) from e
        except Exception as e:
            error_message = f"Unexpected error: {e}"
            logger.debug("Error running Strale component", exc_info=True)
            self.status = error_message
            raise ToolException(error_message) from e

    def build_tool(self) -> Tool:
        if self.tool_mode == "Execute a specific capability":
            return StructuredTool.from_function(
                name="strale_execute",
                description=(f"Execute the Strale '{self.capability_slug}' capability. Pass inputs as a JSON string."),
                func=self._tool_execute_specific,
                args_schema=ExecuteCapabilitySchema,
            )
        return StructuredTool.from_function(
            name="strale_search_and_execute",
            description=(
                "Search Strale's capability catalog and execute the best match. "
                "Covers company verification, sanctions screening, VAT validation, invoice extraction, "
                "and more. Describe what data you need in natural language."
            ),
            func=self._tool_search_and_execute,
            args_schema=SearchAndExecuteSchema,
        )

    def _tool_search_and_execute(self, task: str, inputs: str | None = None) -> list[Data]:
        """StructuredTool entry point for search-and-execute mode."""
        try:
            return self._search_and_execute(task, inputs)
        except Exception as e:
            error_message = f"Strale error: {e}"
            logger.debug("Error in strale_search_and_execute tool", exc_info=True)
            raise ToolException(error_message) from e

    def _tool_execute_specific(self, inputs: str) -> list[Data]:
        """StructuredTool entry point for execute-specific mode."""
        try:
            return self._execute_specific(inputs)
        except Exception as e:
            error_message = f"Strale error: {e}"
            logger.debug("Error in strale_execute tool", exc_info=True)
            raise ToolException(error_message) from e
