"""Tool component for retrieving claim and authorization history."""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from langchain_core.tools import StructuredTool, ToolException
from datetime import datetime
import asyncio
import traceback

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.custom.custom_component.component import Input
from langflow.schema import Data
from langflow.logging import logger
from langflow.custom.genesis.services.deps import get_claim_auth_history_service


class ClaimHistorySchema(BaseModel):
    """Schema for the claim history tool."""

    member_id: str = Field(
        ...,
        description="Member ID to retrieve claim history for",
    )
    start_date: Optional[str] = Field(
        None,
        description="Start date for claim history (ISO format, e.g., '2023-01-01'). If not provided, defaults to 12 months ago.",
    )
    end_date: Optional[str] = Field(
        None,
        description="End date for claim history (ISO format, e.g., '2023-12-31'). If not provided, defaults to current date.",
    )
    limit: Optional[int] = Field(
        10,
        description="Maximum number of claims to retrieve",
    )


class AuthHistorySchema(BaseModel):
    """Schema for the authorization history tool."""

    member_id: str = Field(
        ...,
        description="Member ID to retrieve authorization history for",
    )
    start_date: Optional[str] = Field(
        None,
        description="Start date for authorization history (ISO format, e.g., '2023-01-01'). If not provided, defaults to 12 months ago.",
    )
    end_date: Optional[str] = Field(
        None,
        description="End date for authorization history (ISO format, e.g., '2023-12-31'). If not provided, defaults to current date.",
    )
    limit: Optional[int] = Field(
        10,
        description="Maximum number of authorizations to retrieve",
    )


class QNextAuthHistoryTool(LCToolComponent):
    """Tool component for retrieving claim and authorization history."""

    display_name: str = "QNXT"
    description: str = (
        "Retrieve claim and authorization history for a member from QNext."
    )
    icon: str = "Autonomize"
    name: str = "QNextAuthHistoryTool"

    inputs = [
        Input(
            name="default_member_id",
            display_name="Default Member ID",
            info="Default member ID to retrieve history for (optional).",
            required=False,
            tool_mode=True,
        ),
        Input(
            name="default_start_date",
            display_name="Default Start Date",
            info="Default start date in ISO format (e.g., '2023-01-01').",
            required=False,
            tool_mode=True,
        ),
        Input(
            name="default_end_date",
            display_name="Default End Date",
            info="Default end date in ISO format (e.g., '2023-12-31').",
            required=False,
            tool_mode=True,
        ),
        Input(
            name="default_limit",
            display_name="Default Limit",
            info="Default maximum number of records to retrieve.",
            required=False,
            field_type="int",
            tool_mode=True,
        ),
    ]

    def __init__(self, **kwargs):
        """Initialize the Claim & Auth History Tool component."""
        super().__init__(**kwargs)

    @property
    def history_service(self):
        """Get the Claim & Auth History service."""
        return get_claim_auth_history_service()

    async def get_claim_history(
        self,
        member_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> Dict[str, Any]:
        """
        Retrieve claim history for a member.
        """
        logger.info(f"Getting claim history for member ID: {member_id}")

        try:
            # Validate member ID
            if not member_id:
                raise ValueError("Member ID is required")

            # Validate limit
            if limit is not None and (not isinstance(limit, int) or limit < 1):
                limit = 10

            # Call the service
            result = await self.history_service.get_claim_history(
                member_id=member_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )

            # Process the result for better usability
            summary = self._create_claim_summary(result)
            result["summary"] = summary

            return result

        except Exception as e:
            logger.error(f"Error getting claim history: {e}")
            # Return structured error response instead of raising
            return {
                "error": str(e),
                "member_id": member_id,
                "claims": [],
                "total_count": 0,
                "summary": {
                    "total_claims": 0,
                    "status_counts": {},
                    "service_codes": {},
                },
            }

    async def get_auth_history(
        self,
        member_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> Dict[str, Any]:
        """
        Retrieve authorization history for a member.
        """
        logger.info(f"Getting authorization history for member ID: {member_id}")

        try:
            # Validate member ID
            if not member_id:
                raise ValueError("Member ID is required")

            # Validate limit
            if limit is not None and (not isinstance(limit, int) or limit < 1):
                limit = 10

            # Call the service
            result = await self.history_service.get_auth_history(
                member_id=member_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )

            # Process the result for better usability
            summary = self._create_auth_summary(result)
            result["summary"] = summary

            return result

        except Exception as e:
            logger.error(f"Error getting authorization history: {e}")
            # Return structured error response instead of raising
            return {
                "error": str(e),
                "member_id": member_id,
                "authorizations": [],
                "total_count": 0,
                "summary": {
                    "total_authorizations": 0,
                    "status_counts": {},
                    "service_codes": {},
                },
            }

    def _create_claim_summary(self, claim_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summary of claim data for easier consumption.
        """
        claims = claim_data.get("claims", [])

        # Count claims by status - ensure status is a string to avoid unhashable issues
        status_counts = {}
        for claim in claims:
            status = str(claim.get("status", "Unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count unique service codes - ensure code is a string
        service_codes = {}
        for claim in claims:
            for service in claim.get("services", []):
                code = str(service.get("service_code", "Unknown"))
                service_codes[code] = service_codes.get(code, 0) + 1

        # Calculate total amounts
        total_billed = sum(claim.get("total_billed", 0) for claim in claims)
        total_paid = sum(claim.get("total_paid", 0) for claim in claims)

        # Return the summary
        return {
            "total_claims": len(claims),
            "status_counts": status_counts,
            "service_codes": service_codes,
            "total_billed": round(total_billed, 2) if total_billed else 0,
            "total_paid": round(total_paid, 2) if total_paid else 0,
            "payment_ratio": (
                round(total_paid / total_billed, 2) if total_billed > 0 else 0
            ),
        }

    def _create_auth_summary(self, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a summary of authorization data for easier consumption.
        """
        auths = auth_data.get("authorizations", [])

        # Count authorizations by status - ensure status is a string
        status_counts = {}
        for auth in auths:
            status = str(auth.get("status", "Unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count unique service codes - ensure code is a string
        service_codes = {}
        for auth in auths:
            for service in auth.get("services", []):
                code = str(service.get("service_code", "Unknown"))
                service_codes[code] = service_codes.get(code, 0) + 1

        # Count active vs. expired auths
        now = datetime.now().strftime("%Y-%m-%d")
        active_count = 0
        for auth in auths:
            auth_period = auth.get("auth_period", {})
            end_date = auth_period.get("end_date", "")
            if end_date >= now:
                active_count += 1

        # Return the summary
        return {
            "total_authorizations": len(auths),
            "active_authorizations": active_count,
            "expired_authorizations": len(auths) - active_count,
            "status_counts": status_counts,
            "service_codes": service_codes,
        }

    def build_tool(self) -> List[Tool]:
        """Build the claim and auth history tools for use by an agent."""

        # Create synchronous wrapper for async functions
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
                    # Return a structured result with error information
                    error_response = {
                        "error": str(e),
                        "system_error": True,
                        "member_id": (
                            args[0] if args else kwargs.get("member_id", "unknown")
                        ),
                    }

                    # Add specific fields based on which function failed
                    if async_func.__name__ == "get_claim_history":
                        error_response.update(
                            {
                                "claims": [],
                                "total_count": 0,
                                "summary": {
                                    "total_claims": 0,
                                    "service_codes": {},
                                    "status_counts": {},
                                },
                            }
                        )
                    elif async_func.__name__ == "get_auth_history":
                        error_response.update(
                            {
                                "authorizations": [],
                                "total_count": 0,
                                "summary": {
                                    "total_authorizations": 0,
                                    "service_codes": {},
                                    "status_counts": {},
                                },
                            }
                        )

                    return error_response

            return wrapper

        # Claim history tool with sync wrapper
        claim_tool = StructuredTool.from_function(
            name="get_claim_history",
            description=(
                "Retrieve claim history for a member to analyze past services and payments. "
                "This includes details like dates of service, providers, diagnoses, service codes, and payment statuses."
            ),
            func=sync_wrapper(self.get_claim_history),
            args_schema=ClaimHistorySchema,
        )

        # Auth history tool with sync wrapper
        auth_tool = StructuredTool.from_function(
            name="get_authorization_history",
            description=(
                "Retrieve authorization history for a member to analyze past and current authorizations. "
                "This includes details like authorization dates, requesting providers, diagnoses, service codes, and statuses."
            ),
            func=sync_wrapper(self.get_auth_history),
            args_schema=AuthHistorySchema,
        )

        return [claim_tool, auth_tool]

    def run_model(self) -> list[Data]:
        """Run the tool directly with the component's inputs, for API/direct use."""
        # Get values from UI inputs or use defaults
        member_id = (
            self.default_member_id
            if hasattr(self, "default_member_id") and self.default_member_id
            else None
        )
        start_date = (
            self.default_start_date
            if hasattr(self, "default_start_date") and self.default_start_date
            else None
        )
        end_date = (
            self.default_end_date
            if hasattr(self, "default_end_date") and self.default_end_date
            else None
        )
        limit = (
            self.default_limit
            if hasattr(self, "default_limit") and self.default_limit
            else 10
        )

        if not member_id:
            return [
                Data(
                    data={"error": "No member ID provided"},
                    text="Error: No member ID provided",
                )
            ]

        try:
            # Create a dedicated event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run both functions in the same event loop
                claim_future = self.get_claim_history(
                    member_id=member_id,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                )

                auth_future = self.get_auth_history(
                    member_id=member_id,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                )

                # Run both concurrently
                claim_result, auth_result = loop.run_until_complete(
                    asyncio.gather(claim_future, auth_future)
                )
            finally:
                loop.close()

            # Safely handle results
            if not isinstance(claim_result, dict):
                claim_result = {
                    "error": "Invalid claim result format",
                    "claims": [],
                    "summary": {"total_claims": 0},
                }

            if not isinstance(auth_result, dict):
                auth_result = {
                    "error": "Invalid auth result format",
                    "authorizations": [],
                    "summary": {"total_authorizations": 0},
                }

            # Combine results
            combined_result = {
                "member_id": member_id,
                "date_range": {"start_date": start_date, "end_date": end_date},
                "claims": claim_result,
                "authorizations": auth_result,
            }

            # Format the result as a list of Data objects
            text = f"Retrieved claim and auth history for member {member_id}."
            if "summary" in claim_result:
                text += (
                    f" Found {claim_result['summary'].get('total_claims', 0)} claims"
                )
            if "summary" in auth_result:
                text += f" and {auth_result['summary'].get('total_authorizations', 0)} authorizations."

            return [Data(data=combined_result, text=text)]

        except Exception as e:
            logger.error(f"Error retrieving claim and authorization history: {str(e)}")
            logger.error(traceback.format_exc())
            return [
                Data(
                    data={"error": str(e), "member_id": member_id},
                    text=f"Error retrieving claim and authorization history: {str(e)}",
                )
            ]
