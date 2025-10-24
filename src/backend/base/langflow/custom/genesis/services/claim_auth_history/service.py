"""Service for mocking claim and authorization history data."""

import os
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from langflow.services.base import Service


class ClaimAuthHistoryService(Service):
    """Mock service for claim and authorization history data."""

    name = "claim_auth_history_service"

    def __init__(self):
        """Initialize the claim and auth history service."""
        self.use_mock = os.environ.get("USE_MOCK_CLAIM_AUTH", "true").lower() == "true"
        logger.info(f"ClaimAuthHistoryService initialized. Using mock: {self.use_mock}")

    async def get_claim_history(
        self,
        member_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Get claim history for a member.

        Args:
            member_id: Member ID
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            limit: Maximum number of claims to return

        Returns:
            Dictionary containing claim history in the new format
        """
        logger.info(f"Getting claim history for member ID: {member_id}")

        if not self.use_mock:
            # In a real implementation, this would call an external API
            logger.warning(
                "Non-mock claim history not implemented. Falling back to mock data."
            )

        # Parse dates or use defaults (last 12 months to present)
        end = datetime.now()
        if end_date:
            try:
                end = datetime.fromisoformat(end_date)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid end_date format: {end_date}. Using current date."
                )

        start = end - timedelta(days=365)  # Default to last 12 months
        if start_date:
            try:
                start = datetime.fromisoformat(start_date)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid start_date format: {start_date}. Using 12 months before end date."
                )

        # Generate mock claim data in new format
        claims = self._generate_mock_claims_new_format(member_id, start, end, limit)

        result = {
            "member_id": member_id,
            "query_period": {
                "start_date": start.strftime("%m/%d/%Y"),
                "end_date": end.strftime("%m/%d/%Y"),
            },
            "claims_history": claims,
            "total_count": len(claims),
            "has_more": False,
        }

        return result

    async def get_auth_history(
        self,
        member_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Get authorization history for a member.

        Args:
            member_id: Member ID
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            limit: Maximum number of authorizations to return

        Returns:
            Dictionary containing authorization history in the new format
        """
        logger.info(f"Getting authorization history for member ID: {member_id}")

        if not self.use_mock:
            # In a real implementation, this would call an external API
            logger.warning(
                "Non-mock auth history not implemented. Falling back to mock data."
            )

        # Parse dates or use defaults (last 12 months to present)
        end = datetime.now()
        if end_date:
            try:
                end = datetime.fromisoformat(end_date)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid end_date format: {end_date}. Using current date."
                )

        start = end - timedelta(days=365)  # Default to last 12 months
        if start_date:
            try:
                start = datetime.fromisoformat(start_date)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid start_date format: {start_date}. Using 12 months before end date."
                )

        # Generate mock auth data in new format
        auths = self._generate_mock_auths_new_format(member_id, start, end, limit)

        result = {
            "member_id": member_id,
            "query_period": {
                "start_date": start.strftime("%m/%d/%Y"),
                "end_date": end.strftime("%m/%d/%Y"),
            },
            "auths_history": auths,
            "total_count": len(auths),
            "has_more": False,
        }

        return result

    def _generate_mock_claims_new_format(
        self, member_id: str, start_date: datetime, end_date: datetime, limit: int
    ) -> List[Dict[str, Any]]:
        """
        Generate mock claim data in the new format.
        """
        # Common CPT/HCPCS codes for demo purposes
        service_data = [
            {"code": "97110", "type": "Physical Therapy", "description": "Therapeutic exercises"},
            {"code": "97112", "type": "Physical Therapy", "description": "Neuromuscular reeducation"},
            {"code": "97116", "type": "Physical Therapy", "description": "Gait training"},
            {"code": "97140", "type": "Physical Therapy", "description": "Manual therapy"},
            {"code": "92507", "type": "Speech Therapy", "description": "Speech/language treatment"},
            {"code": "97530", "type": "Occupational Therapy", "description": "Therapeutic activities"},
            {"code": "99213", "type": "Office Visit", "description": "Office visit - established patient"},
            {"code": "99214", "type": "Office Visit", "description": "Office visit - established patient"},
            {"code": "70450", "type": "Radiology", "description": "CT head without contrast"},
            {"code": "73721", "type": "Radiology", "description": "MRI lower extremity"},
        ]

        # Common diagnoses
        diagnoses_data = [
            {"code": "M54.5", "description": "Low back pain"},
            {"code": "M25.511", "description": "Pain in right shoulder"},
            {"code": "G93.1", "description": "Anoxic brain damage, not elsewhere classified"},
            {"code": "I69.351", "description": "Hemiplegia following cerebral infarction"},
            {"code": "S72.001A", "description": "Fracture of unspecified part of neck of right femur"},
            {"code": "F80.1", "description": "Expressive language disorder"},
            {"code": "R47.02", "description": "Dysarthria and anarthria"},
        ]

        # States and LOBs
        states = ["CA", "TX", "FL", "NY", "WA"]
        lobs = ["Medicare", "Medicaid", "Marketplace"]
        
        claims = []
        date_range = (end_date - start_date).days
        num_claims = min(limit, max(1, date_range // 30))  # Roughly monthly claims

        for i in range(num_claims):
            # Generate random service date
            days_offset = random.randint(0, max(1, date_range))
            service_start = start_date + timedelta(days=days_offset)
            service_end = service_start + timedelta(days=random.randint(0, 14))  # Service period

            # Select random service
            service_info = random.choice(service_data)
            diagnosis_info = random.choice(diagnoses_data)
            
            # Generate claim
            claim = {
                "claim_id": f"CLM{random.randint(1000, 9999)}",
                "claim_status": random.choice(["Approved", "Processed", "Denied", "Pending"]),
                "start_date": service_start.strftime("%m/%d/%Y"),
                "end_date": service_end.strftime("%m/%d/%Y"),
                "services": [
                    {
                        "code": service_info["code"],
                        "type": service_info["type"],
                        "description": service_info["description"],
                        "units_requested": str(random.randint(1, 12)),  # String format as per example
                        "start_date": service_start.strftime("%m/%d/%Y"),
                        "end_date": service_end.strftime("%m/%d/%Y")
                    }
                ],
                "diagnoses": [diagnosis_info],
                "member_details": {
                    "member_id": member_id,
                    "member_plan_id": f"PLAN{random.randint(10000, 99999)}",
                    "rate_code": f"{random.randint(1, 999):03d}",
                    "state": random.choice(states),
                    "line_of_business": random.choice(lobs)
                }
            }
            claims.append(claim)

        # Sort by start date (newest first)
        claims.sort(key=lambda x: datetime.strptime(x["start_date"], "%m/%d/%Y"), reverse=True)
        
        return claims

    def _generate_mock_auths_new_format(
        self, member_id: str, start_date: datetime, end_date: datetime, limit: int
    ) -> List[Dict[str, Any]]:
        """
        Generate mock authorization data in the new format.
        """
        # Common service codes for authorizations
        service_data = [
            {"code": "97110", "type": "Physical Therapy", "description": "Therapeutic exercises"},
            {"code": "97112", "type": "Physical Therapy", "description": "Neuromuscular reeducation"},
            {"code": "97116", "type": "Physical Therapy", "description": "Gait training"},
            {"code": "97140", "type": "Physical Therapy", "description": "Manual therapy"},
            {"code": "92507", "type": "Speech Therapy", "description": "Speech/language treatment"},
            {"code": "97530", "type": "Occupational Therapy", "description": "Therapeutic activities"},
            {"code": "70450", "type": "Radiology", "description": "CT head without contrast"},
            {"code": "73721", "type": "Radiology", "description": "MRI lower extremity"},
            {"code": "95810", "type": "Sleep Study", "description": "Polysomnography"},
            {"code": "58571", "type": "Surgery", "description": "Laparoscopic procedure"},
        ]

        # Common diagnoses
        diagnoses_data = [
            {"code": "M54.5", "description": "Low back pain"},
            {"code": "M25.511", "description": "Pain in right shoulder"},
            {"code": "G93.1", "description": "Anoxic brain damage, not elsewhere classified"},
            {"code": "I69.351", "description": "Hemiplegia following cerebral infarction"},
            {"code": "S72.001A", "description": "Fracture of unspecified part of neck of right femur"},
            {"code": "F80.1", "description": "Expressive language disorder"},
            {"code": "R47.02", "description": "Dysarthria and anarthria"},
        ]

        # States and LOBs
        states = ["CA", "TX", "FL", "NY", "WA"]
        lobs = ["Medicare", "Medicaid", "Marketplace"]
        
        auths = []
        date_range = (end_date - start_date).days
        num_auths = min(limit, max(1, date_range // 60))  # Roughly bi-monthly auths

        for i in range(num_auths):
            # Generate random request date
            days_offset = random.randint(0, max(1, date_range))
            request_date = start_date + timedelta(days=days_offset)
            
            # Auth period
            auth_start = request_date + timedelta(days=random.randint(1, 14))
            auth_end = auth_start + timedelta(days=random.randint(30, 90))

            # Select random service and diagnosis
            service_info = random.choice(service_data)
            diagnosis_info = random.choice(diagnoses_data)
            
            # Generate authorization
            auth = {
                "auth_request": {
                    "case_id": f"AUTH{random.randint(1000, 9999)}",
                    "auth_details": {
                        "services": [
                            {
                                "code": service_info["code"],
                                "type": service_info["type"],
                                "description": service_info["description"],
                                "units_requested": str(random.randint(1, 20)),
                                "start_date": auth_start.strftime("%m/%d/%Y"),
                                "end_date": auth_end.strftime("%m/%d/%Y")
                            }
                        ],
                        "diagnoses": [diagnosis_info]
                    },
                    "auth_submission_date": request_date.strftime("%m/%d/%Y"),
                    "member_details": {
                        "member_id": member_id,
                        "member_plan_id": f"PLAN{random.randint(10000, 99999)}",
                        "rate_code": f"RC{random.randint(100, 999)}",
                        "state": random.choice(states),
                        "line_of_business": random.choice(lobs)
                    }
                },
                "auth_validation_status": random.choice(["Approved", "Partially Approved", "Pending", "Denied"])
            }
            auths.append(auth)

        # Sort by submission date (newest first)
        auths.sort(key=lambda x: datetime.strptime(x["auth_request"]["auth_submission_date"], "%m/%d/%Y"), reverse=True)
        
        return auths