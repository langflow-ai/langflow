"""Tool component for checking Prior Authorization requirements for service codes."""

from typing import Any, Dict, List

from langchain_core.tools import StructuredTool, ToolException
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import MessageTextInput
from langflow.logging import logger
from langflow.schema.data import Data
from pydantic import BaseModel, Field

from langflow.custom.genesis.services.deps import get_pa_lookup_service


class PALookupTool(LCToolComponent):
    """Tool component for checking Prior Authorization requirements for service codes."""

    display_name: str = "PA Lookup"
    description: str = (
        "Check if Prior Authorization is required for specific service codes."
    )
    icon: str = "Autonomize"
    name: str = "PALookupTool"

    class PALookupSchema(BaseModel):
        """Schema for the PA Lookup tool."""

        service_codes: List[str] = Field(
            ...,
            description="List of service codes to check for Prior Authorization requirements",
            examples=[["95810"], ["58571", "38900"]],
        )
        lob: str = Field(
            ...,
            description="Line of Business: Medicare, Medicaid, or Marketplace",
            examples=["Medicare", "Medicaid", "Marketplace"],
        )
        state: str = Field(
            ...,
            description="Two-letter state code (e.g., MI for Michigan, WA for Washington)",
            examples=["MI", "WA", "CA"],
        )

    inputs = [
        MessageTextInput(
            name="default_service_codes",
            display_name="Default Service Codes",
            info="Default service codes to check for PA requirements (comma-separated).",
            tool_mode=True,
        ),
        MessageTextInput(
            name="default_lob",
            display_name="Default Line of Business",
            info="Default Line of Business (Medicare, Medicaid, Marketplace).",
            tool_mode=True,
        ),
        MessageTextInput(
            name="default_state",
            display_name="Default State",
            info="Default two-letter state code.",
            tool_mode=True,
        ),
    ]

    def __init__(self, **kwargs):
        """Initialize the PA Lookup Tool component."""
        super().__init__(**kwargs)

    @property
    def pa_lookup_service(self):
        """Get the PA Lookup service."""
        return get_pa_lookup_service()

    async def check_pa_requirements(
        self, service_codes: List[str], lob: str, state: str
    ) -> Dict[str, Any]:
        """
        Check if prior authorization is required for the specified service codes.

        Args:
            service_codes: List of service codes to check
            lob: Line of Business (Medicare, Medicaid, Marketplace)
            state: Two-letter state code

        Returns:
            Dictionary containing PA status for each code and other details
        """
        logger.info(
            f"Checking PA requirements for codes: {service_codes}, LOB: {lob}, State: {state}"
        )

        try:
            # Normalize inputs
            clean_codes = [code.strip() for code in service_codes]
            clean_lob = lob.strip().title()  # Ensure proper capitalization
            clean_state = state.strip().upper()

            # Validate LOB
            if clean_lob not in ["Medicare", "Medicaid", "Marketplace"]:
                raise ValueError(
                    f"Invalid Line of Business: {lob}. Must be Medicare, Medicaid, or Marketplace."
                )

            # Validate state (simplified validation - in production, use a comprehensive list)
            if len(clean_state) != 2 or not clean_state.isalpha():
                raise ValueError(
                    f"Invalid state code: {state}. Must be a two-letter state code (e.g., MI, WA)."
                )

            # Call the service
            result = await self.pa_lookup_service.check_pa_status(
                codes=clean_codes, lob=clean_lob, state=clean_state
            )

            # Process the result for better readability for the agent
            simplified_result = self._simplify_pa_result(result)

            return simplified_result

        except Exception as e:
            logger.error(f"Error checking PA requirements: {e}")
            raise ToolException(f"Error checking PA requirements: {str(e)}")

    def _simplify_pa_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simplify the PA lookup result for easier consumption by the agent.

        Args:
            result: Raw PA lookup result

        Returns:
            Simplified result
        """
        simplified = {"status": result.get("message", "Unknown"), "codes": {}}

        # Extract PA status for each code
        pa_data_group = result.get("paStatusDataGrp", {})
        pa_required_data = pa_data_group.get("paRequiredData", [])

        for code_data in pa_required_data:
            code = code_data.get("Code", "Unknown")
            pa_status = code_data.get("paStatus", "Unknown")
            description = code_data.get("codeDesc", "")

            # Simplify the PA status for easier interpretation
            is_required = "Required" in pa_status
            has_exclusions = "Exclusions" in pa_status

            simplified["codes"][code] = {
                "description": description,
                "pa_required": is_required,
                "has_exclusions": has_exclusions,
                "full_status": pa_status,
            }

        return simplified

    def build_tool(self) -> Tool:
        """Build the PA Lookup tool for use by an agent."""

        # Create synchronous wrapper for async function
        def sync_wrapper(async_func):
            def wrapper(*args, **kwargs):
                try:
                    import asyncio

                    # Create a new event loop for each call
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        return loop.run_until_complete(async_func(*args, **kwargs))
                    finally:
                        loop.close()
                except Exception as e:
                    logger.error(f"Error in {async_func.__name__}: {str(e)}")
                    # Return structured error response
                    return {
                        "error": str(e),
                        "status": "Error",
                        "codes": {},
                        "service_codes": kwargs.get("service_codes", []),
                        "lob": kwargs.get("lob", ""),
                        "state": kwargs.get("state", ""),
                        "system_error": True,
                    }

            return wrapper

        return StructuredTool.from_function(
            name="check_prior_authorization",
            description="Check if Prior Authorization (PA) is required for specific service codes based on Line of Business (Medicare, Medicaid, Marketplace) and state.",
            func=sync_wrapper(self.check_pa_requirements),
            args_schema=self.PALookupSchema,
        )

    def run_model(self) -> list[Data]:
        """Run the tool directly with the component's inputs, for API/direct use."""
        # Get values from UI inputs or use defaults
        service_codes_str = (
            self.default_service_codes
            if hasattr(self, "default_service_codes") and self.default_service_codes
            else ""
        )
        service_codes = (
            [code.strip() for code in service_codes_str.split(",")]
            if service_codes_str
            else []
        )

        lob = (
            self.default_lob
            if hasattr(self, "default_lob") and self.default_lob
            else "Medicare"
        )
        state = (
            self.default_state
            if hasattr(self, "default_state") and self.default_state
            else "MI"
        )

        if not service_codes:
            return [
                Data(
                    data={"error": "No service codes provided"},
                    text="Error: No service codes provided",
                )
            ]

        # Get the tool to use its structured functionality
        self.build_tool()

        try:
            import asyncio

            # Create a dedicated event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self.check_pa_requirements(
                        service_codes=service_codes, lob=lob, state=state
                    )
                )
            finally:
                loop.close()

            # Format the result as text
            text_result = (
                f"PA Status Results for {len(service_codes)} service codes\n\n"
            )

            for code, code_info in result.get("codes", {}).items():
                pa_required = (
                    "Required" if code_info.get("pa_required") else "Not Required"
                )
                text_result += f"Code: {code} - {code_info.get('description', '')}\n"
                text_result += f"PA Status: {pa_required}\n"
                if code_info.get("has_exclusions"):
                    text_result += "Note: This code has some exclusions or conditions\n"
                text_result += f"Full Status: {code_info.get('full_status', '')}\n\n"

            return [Data(data=result, text=text_result)]

        except Exception as e:
            error_message = f"Error checking PA requirements: {str(e)}"
            return [Data(data={"error": error_message}, text=error_message)]
