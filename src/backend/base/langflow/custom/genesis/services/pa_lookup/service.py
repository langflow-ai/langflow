"""Service for PA (Prior Authorization) lookup requests."""

import os
import json
import httpx
from typing import Dict, List, Any, Optional, Union
from loguru import logger
from langflow.services.base import Service


class PALookupService(Service):
    """Service to check if Prior Authorization is required for service codes."""

    name = "pa_lookup_service"

    # Configuration
    DEFAULT_ENDPOINT = "https://umpegauat1.molinahealthcare.com/prweb/api/LookupService/v1/GetPAreqstatus"
    DEFAULT_USERNAME = "Testuser"
    DEFAULT_PASSWORD = "rules@123"

    def __init__(self):
        """Initialize the PA Lookup Service."""
        self.use_mock = os.environ.get("USE_MOCK_PA_LOOKUP", "true").lower() == "true"
        self.endpoint = os.environ.get("PA_LOOKUP_ENDPOINT", self.DEFAULT_ENDPOINT)
        self.username = os.environ.get("PA_LOOKUP_USERNAME", self.DEFAULT_USERNAME)
        self.password = os.environ.get("PA_LOOKUP_PASSWORD", self.DEFAULT_PASSWORD)
        logger.info(f"PALookupService initialized. Using mock: {self.use_mock}")

    async def check_pa_status(
        self,
        codes: List[str],
        lob: str,
        state: str,
        hp_code: Optional[str] = None,
        hp_name: Optional[str] = None,
        consumer_name: str = "Availity",
    ) -> Dict[str, Any]:
        """
        Check if Prior Authorization is required for the given service codes.

        Args:
            codes: List of service codes to check
            lob: Line of Business ('Medicare', 'Medicaid', 'Marketplace')
            state: State code (e.g., 'MI', 'WA')
            hp_code: Health Plan code (optional)
            hp_name: Health Plan name (optional)
            consumer_name: Consumer name (default: 'Availity')

        Returns:
            Dictionary containing PA status information
        """
        # Derive hp_code and hp_name if not provided
        if not hp_code:
            hp_code = f"{state}-MHI"

        if not hp_name:
            hp_name = f"Molina Healthcare of {state}"

        # Timestamp construction
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S.%f")[:-3]

        # Transaction ID construction
        transaction_id = f"AVPAST{datetime.now().strftime('%Y%m%d%H%M%S%f')}"[:32]

        # Request data
        request_data = {
            "consumerName": consumer_name,
            "hpCode": hp_code,
            "hpName": hp_name,
            "state": state,
            "transactionID": transaction_id,
            "timeStamp": timestamp,
            "codes": codes,
            "LOB": lob,
        }

        if self.use_mock:
            logger.info(
                f"Using mock PA lookup for codes: {codes}, LOB: {lob}, state: {state}"
            )
            return await self._mock_pa_lookup(request_data)
        else:
            logger.info(
                f"Calling real PA lookup API for codes: {codes}, LOB: {lob}, state: {state}"
            )
            return await self._real_pa_lookup(request_data)

    async def _real_pa_lookup(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a real API call to the PA lookup service."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.endpoint,
                    json=request_data,
                    auth=(self.username, self.password),
                    timeout=30.0,
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during PA lookup: {e}")
            return {
                "message": f"API Error: {str(e)}",
                "statusCode": str(e.response.status_code),
                "transactionID": request_data.get("transactionID", ""),
            }
        except Exception as e:
            logger.error(f"Error during PA lookup: {e}")
            return {
                "message": f"Error: {str(e)}",
                "statusCode": "500",
                "transactionID": request_data.get("transactionID", ""),
            }

    async def _mock_pa_lookup(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock PA lookup response based on the request data."""
        codes = request_data.get("codes", [])
        lob = request_data.get("LOB", "")
        state = request_data.get("state", "")

        pa_required_data = []

        # Generate mock data for each code
        for code in codes:
            # Determine PA status based on some simple rules for the mock
            # Uses code value to create deterministic but varied responses
            is_covered = True
            if code.startswith("9"):  # Example rule: codes starting with 9 require PA
                pa_status = "Required"
            elif (
                sum(int(digit) for digit in code if digit.isdigit()) % 3 == 0
            ):  # Divisible by 3
                pa_status = "Prior Authorization Not Required"
            else:
                pa_status = "Prior Authorization Not Required \n*Exclusions Apply"

            code_info = {
                "paStatus": pa_status,
                "codeDesc": self._get_mock_code_description(code),
                "vendorUrl": "",
                "IsVendorDelegated": "N",
                "paDisclaimer": self._get_mock_disclaimer(pa_status),
                "Code": code,
                "stateNotes": "",
                "paMHINotes": "",
            }

            pa_required_data.append(code_info)

        return {
            "paStatusDataGrp": {"paRequiredData": pa_required_data},
            "message": "Success",
            "transactionID": request_data.get("transactionID", ""),
            "statusCode": "200",
        }

    def _get_mock_code_description(self, code: str) -> str:
        """Generate a mock description for a service code."""
        descriptions = {
            # CPT Codes
            "95810": "POLYSOM 6 OR GT YRS SLEEP 4 OR GT ADDL PARAM ATTND",
            "58571": "LAPS TOTAL HYSTERECT 250 GM OR LT W/RMVL TUBE/OVARY",
            "38900": "INTRAOP SENTINEL LYMPH NODE ID W/DYE INJECTION",
            # Add more known codes as needed
        }

        # Return known description or generate a placeholder
        return descriptions.get(code, f"PROCEDURE CODE {code} - MOCK DESCRIPTION")

    def _get_mock_disclaimer(self, pa_status: str) -> str:
        """Generate appropriate disclaimer based on PA status."""
        if pa_status == "Required":
            return '<p><span style="font-family:Arial,Helvetica,sans-serif;"><span style="font-size:14px;">*Prior authorization required where covered. </span></span></p>'
        elif "Exclusions" in pa_status:
            return '<p><span style="font-size:14px;"><span style="font-family:Arial,Helvetica,sans-serif;">*Exclusions:</span></span></p>\n\n<ul>\n\t<li style="font-size: 14px;"><span style="font-size:14px;"><span style="font-family:Arial,Helvetica,sans-serif;">Non-Participating Provider Requests</span></span></li>\n\t<li style="font-size: 14px;"><span style="font-size:14px;"><span style="font-family:Arial,Helvetica,sans-serif;">Non-Covered Codes</span></span></li>\n</ul>\n\n<p><span style="font-size:14px;"><span style="font-family:Arial,Helvetica,sans-serif;">*The presence of a code on this tool should not be used to determine whether a service is covered.&nbsp; Refer to your regulatory agency for benefit coverage and non-covered codes.</span></span></p>'
        else:
            return '<p><span style="font-size:14px;"><span style="font-family:Arial,Helvetica,sans-serif;">*Prior Authorization is not a guarantee of payment for services.</span></span></p>'
