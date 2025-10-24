"""Tool component for checking service code information and coverage using Encoder Pro."""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from langchain_core.tools import StructuredTool, ToolException

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import MessageTextInput
from langflow.schema import Data
from langflow.logging import logger
from langflow.custom.genesis.services.deps import get_encoder_pro_service


class EncoderProTool(LCToolComponent):
    """Tool component for checking service code information and coverage using Encoder Pro."""

    display_name: str = "Encoder Pro"
    description: str = "Get information and coverage status for service codes."
    icon: str = "Autonomize"
    name: str = "EncoderProTool"

    class CodeInfoSchema(BaseModel):
        """Schema for the Encoder Pro code information tool."""

        service_code: str = Field(
            ...,
            description="Service code to check (CPT or HCPCS)",
            examples=["95810", "J7352"],
        )
        check_coverage: bool = Field(
            True,
            description="Whether to check Medicare coverage status",
        )

    inputs = [
        MessageTextInput(
            name="default_service_code",
            display_name="Default Service Code",
            info="Default service code to check.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="default_check_coverage",
            display_name="Check Coverage",
            info="Whether to check Medicare coverage status by default (true/false).",
            tool_mode=True,
        ),
    ]

    def __init__(self, **kwargs):
        """Initialize the Encoder Pro Tool component."""
        super().__init__(**kwargs)

    async def get_code_info(
        self, service_code: str, check_coverage: bool = True
    ) -> Dict[str, Any]:
        """
        Get detailed information about a service code including description and coverage status.

        Args:
            service_code: The CPT or HCPCS code to check
            check_coverage: Whether to check Medicare coverage status

        Returns:
            Dictionary containing code information and coverage status
        """
        logger.info(
            f"Getting information for service code: {service_code}, check coverage: {check_coverage}"
        )

        try:
            # Normalize input
            clean_code = service_code.strip()

            # Validate the code format (basic validation)
            if not clean_code:
                raise ValueError("Service code cannot be empty")

            # Determine code type
            code_type = self._determine_code_type(clean_code)

            # Get combined result
            result = {
                "code": clean_code,
                "code_type": code_type.upper(),
            }

            # Get description
            try:
                description_data = (
                    await get_encoder_pro_service().get_layman_description(
                        code_type, clean_code
                    )
                )
                result["description"] = description_data.get(
                    "descriptionLay", "Description not available"
                )
                result["technical_description"] = description_data.get(
                    "description", ""
                )
            except Exception as e:
                logger.error(f"Error getting description for code {clean_code}: {e}")
                result["description"] = "Error retrieving description"
                result["description_error"] = str(e)

            # Check coverage if requested
            if check_coverage:
                try:
                    is_covered, coverage_data = (
                        await get_encoder_pro_service().check_code_coverage(clean_code)
                    )
                    result["is_covered"] = is_covered
                    result["coverage_details"] = coverage_data

                    # Extract color codes for easier access
                    if "colorCodes" in coverage_data:
                        result["color_codes"] = coverage_data["colorCodes"]

                except Exception as e:
                    logger.error(f"Error checking coverage for code {clean_code}: {e}")
                    result["is_covered"] = None
                    result["coverage_error"] = str(e)

            return result

        except Exception as e:
            logger.error(f"Error getting code information: {e}")
            raise ToolException(f"Error getting code information: {str(e)}")

    def _determine_code_type(self, code: str) -> str:
        """
        Determine the code type (CPT or HCPCS) based on the code format.

        Args:
            code: The code to evaluate

        Returns:
            Code type ('cpt' or 'hcpcs')
        """
        # Simple heuristic - could be improved for production
        if code.isdigit() and len(code) == 5:
            return "cpt"
        else:
            return "hcpcs"

    def build_tool(self) -> Tool:
        """Build the Encoder Pro tool for use by an agent."""

        # Create synchronous wrapper for async function
        def sync_wrapper(async_func):
            def wrapper(*args, **kwargs):
                try:
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
                        "code": kwargs.get("service_code", "unknown"),
                        "code_type": "Unknown",
                        "description": "Error retrieving code information",
                        "is_covered": None,
                        "system_error": True,
                    }

            return wrapper

        return StructuredTool.from_function(
            name="get_service_code_info",
            description=(
                "Get detailed information about a medical service code (CPT or HCPCS), "
                "including its description and Medicare coverage status. "
                "Use this to understand what a specific code means and whether it's covered."
            ),
            func=sync_wrapper(self.get_code_info),
            args_schema=self.CodeInfoSchema,
        )

    def run_model(self) -> list[Data]:
        """Run the tool directly with the component's inputs, for API/direct use."""
        # Get values from UI inputs or use defaults
        service_code = (
            self.default_service_code
            if hasattr(self, "default_service_code") and self.default_service_code
            else ""
        )

        # Parse check_coverage from string to boolean
        check_coverage_str = (
            self.default_check_coverage
            if hasattr(self, "default_check_coverage") and self.default_check_coverage
            else ""
        )
        check_coverage = True  # Default value
        if check_coverage_str.lower() in ("false", "no", "0", "f", "n"):
            check_coverage = False

        if not service_code:
            return [
                Data(
                    data={"error": "No service code provided"},
                    text="Error: No service code provided",
                )
            ]

        # Get the tool to use its structured functionality
        tool = self.build_tool()

        try:
            import asyncio

            # Create a dedicated event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the async function
                result = loop.run_until_complete(
                    self.get_code_info(
                        service_code=service_code, check_coverage=check_coverage
                    )
                )
            finally:
                loop.close()

            # Format the result as text
            text_result = f"Service Code Information: {service_code} ({result.get('code_type', 'Unknown')})\n\n"
            text_result += f"Description: {result.get('description', 'Unknown')}\n"

            if check_coverage:
                coverage_status = (
                    "Covered" if result.get("is_covered") else "Not Covered"
                )
                if result.get("is_covered") is None:
                    coverage_status = "Coverage status unknown"

                text_result += f"Medicare Coverage: {coverage_status}\n"

                # Add color codes if available
                if "color_codes" in result:
                    color_codes = result["color_codes"]
                    if isinstance(color_codes, list) and color_codes:
                        text_result += "\nColor Codes:\n"
                        for color_code in color_codes:
                            color = color_code.get("colorCode", "Unknown")
                            desc = color_code.get("shortDescription", "")
                            text_result += f"- {color}: {desc}\n"

            return [Data(data=result, text=text_result)]

        except Exception as e:
            error_message = f"Error getting code information: {str(e)}"
            return [Data(data={"error": error_message}, text=error_message)]
