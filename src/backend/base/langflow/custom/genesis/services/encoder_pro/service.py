"""Service for Encoder Pro API integration."""

import os
import httpx
import json
from typing import Dict, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from loguru import logger

from langflow.services.base import Service


class EncoderProService(Service):
    """Service to interact with Encoder Pro API for code information and coverage details."""

    name = "encoder_pro_service"
    # API Configuration
    DEFAULT_TOKEN_ENDPOINT = "https://gateway.optuminsightplatform.com/oauth/token"
    DEFAULT_API_BASE_URL = "https://realtimeecontent.com/ws"
    DEFAULT_CLIENT_ID = "molina_2"
    DEFAULT_CLIENT_SECRET = "ca1a0fcc-dd93-4feb-88af-fb61f1a3180c"

    def __init__(self):
        """Initialize the Encoder Pro Service."""
        self.token_endpoint = os.environ.get(
            "ENCODER_PRO_TOKEN_ENDPOINT", self.DEFAULT_TOKEN_ENDPOINT
        )
        self.api_base_url = os.environ.get(
            "ENCODER_PRO_API_BASE_URL", self.DEFAULT_API_BASE_URL
        )
        self.client_id = os.environ.get("ENCODER_PRO_CLIENT_ID", self.DEFAULT_CLIENT_ID)
        self.client_secret = os.environ.get(
            "ENCODER_PRO_CLIENT_SECRET", self.DEFAULT_CLIENT_SECRET
        )

        self.use_mock = (
            os.environ.get("USE_MOCK_ENCODER_PRO", "false").lower() == "true"
        )

        # Token management
        self._token = None
        self._token_expires_at = None

        logger.info(f"EncoderProService initialized. Using mock: {self.use_mock}")

    async def get_token(self) -> str:
        """
        Get a bearer token for Encoder Pro API.
        Handles token caching and refresh when expired.

        Returns:
            Valid bearer token
        """
        # Check if we have a valid token
        current_time = datetime.now()
        if (
            self._token
            and self._token_expires_at
            and current_time < self._token_expires_at
        ):
            return self._token

        if self.use_mock:
            logger.info("Using mock token for Encoder Pro API")
            self._token = "mock_token"
            self._token_expires_at = current_time + timedelta(hours=1)
            return self._token

        # Get new token
        logger.info("Requesting new token for Encoder Pro API")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_endpoint,
                    headers={
                        "accept": "application/json",
                        "content-type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    timeout=30.0,
                )

                response.raise_for_status()
                token_data = response.json()

                # Extract token and expiry
                self._token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour
                self._token_expires_at = current_time + timedelta(
                    seconds=expires_in - 60
                )  # Buffer of 60 seconds

                return self._token

        except Exception as e:
            logger.error(f"Error getting Encoder Pro token: {e}")
            if self._token:  # Fall back to old token if available
                logger.warning("Falling back to previous token")
                return self._token
            raise ValueError(f"Failed to get Encoder Pro API token: {str(e)}")

    async def get_layman_description(self, code_type: str, code: str) -> Dict[str, Any]:
        """
        Get the layman description for a code.

        Args:
            code_type: Type of code ('cpt', 'hcpcs', 'icd10cm', etc.)
            code: The actual code value

        Returns:
            Dictionary with code description information
        """
        if self.use_mock:
            return await self._mock_layman_description(code_type, code)

        endpoint = (
            f"{self.api_base_url}/codetype/{code_type}/{code}/properties?data=desc-lay"
        )
        return await self._make_api_request(endpoint)

    async def get_color_codes(self, code_type: str, code: str) -> Dict[str, Any]:
        """
        Get color codes and coverage information for a service code.

        Args:
            code_type: Type of code ('cpt' or 'hcpcs')
            code: The actual code value

        Returns:
            Dictionary with coverage and color code information
        """
        if self.use_mock:
            return await self._mock_color_codes(code_type, code)

        if code_type.lower() not in ["cpt", "hcpcs"]:
            raise ValueError(
                f"Color codes only available for 'cpt' or 'hcpcs', got: {code_type}"
            )

        endpoint = f"{self.api_base_url}/codetype/{code_type}/{code}/color-codes"
        return await self._make_api_request(endpoint)

    async def check_code_coverage(self, code: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a code is covered by Medicare, with full details.
        Determines code type (CPT vs HCPCS) automatically.

        Args:
            code: The code to check

        Returns:
            Tuple of (is_covered, full_response_details)
        """
        # Determine if code is CPT or HCPCS based on simple rules
        # This is a simplified approach - in real implementation, you might want more robust detection
        code_type = self._determine_code_type(code)

        # Get color codes which contain coverage information
        response = await self.get_color_codes(code_type, code)

        is_covered = True  # Default to covered

        # Check coverage based on code type
        if code_type.lower() == "cpt":
            is_covered = not response.get("serviceNotCoveredByMedicare", False)
        elif code_type.lower() == "hcpcs":
            is_covered = not response.get("notCoveredOrValidForMedicare", False)

        return is_covered, response

    def _determine_code_type(self, code: str) -> str:
        """
        Determine the code type (CPT or HCPCS) based on the code format.

        Args:
            code: The code to evaluate

        Returns:
            Code type ('cpt' or 'hcpcs')
        """
        # Very simplified detection logic - would need to be expanded for production
        if code.isdigit() and len(code) == 5:
            return "cpt"
        else:
            return "hcpcs"

    async def _make_api_request(self, endpoint: str) -> Dict[str, Any]:
        """Make an authenticated request to the Encoder Pro API."""
        try:
            token = await self.get_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    endpoint,
                    headers={
                        "accept": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                    timeout=30.0,
                )

                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Encoder Pro API call: {e}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error during Encoder Pro API call: {e}")
            return {"error": str(e)}

    async def _mock_layman_description(
        self, code_type: str, code: str
    ) -> Dict[str, Any]:
        """Return mock data for layman description."""
        # Sample mock data structure for layman descriptions
        return {
            "code": code,
            "codeType": code_type.upper(),
            "descriptionLay": f"This is a mock layman description for {code_type.upper()} code {code}",
            "description": f"MOCK TECHNICAL DESCRIPTION FOR {code}",
            "additionalInfo": "Mock additional information",
        }

    async def _mock_color_codes(self, code_type: str, code: str) -> Dict[str, Any]:
        """Return mock data for color codes."""
        # Create deterministic but varied mock data based on the code
        is_covered = not (sum(int(digit) for digit in code if digit.isdigit()) % 5 == 0)

        if code_type.lower() == "cpt":
            return {
                "code": code,
                "codeType": "CPT",
                "serviceNotCoveredByMedicare": not is_covered,
                "colorCodes": [
                    {
                        "colorCode": "RED" if not is_covered else "GREEN",
                        "shortDescription": (
                            "Not covered" if not is_covered else "Covered"
                        ),
                    }
                ],
                "additionalInfo": "This is mock data for demonstration purposes",
            }
        else:  # HCPCS
            return {
                "code": code,
                "codeType": "HCPCS",
                "notCoveredOrValidForMedicare": not is_covered,
                "colorCodes": [
                    {
                        "colorCode": "RED" if not is_covered else "GREEN",
                        "shortDescription": (
                            "Not covered" if not is_covered else "Covered"
                        ),
                    }
                ],
                "additionalInfo": "This is mock data for demonstration purposes",
            }
