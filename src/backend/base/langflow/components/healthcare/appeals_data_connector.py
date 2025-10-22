"""Appeals Data Connector for HIPAA-compliant appeals processing data access.

This component provides unified access to appeals-related databases including denial reasons,
policies, and evidence data for utilization management and appeals processing workflows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.custom.custom_component.component import Component
from langflow.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output, StrInput
from langflow.schema.data import Data
from langflow.schema.message import Message


class AppealsDataConnector(HealthcareConnectorBase):
    """HIPAA-compliant Appeals Data Connector component.

    Provides unified access to appeals-related databases for utilization management
    and appeals processing workflows.

    Features:
    - Denial reasons and decision documentation access
    - Policy database search and matching
    - Clinical evidence and supporting documentation access
    - Appeals processing workflow integration
    - HIPAA-compliant data handling and audit logging
    """

    display_name: str = "Appeals Data Connector"
    description: str = (
        "HIPAA-compliant appeals data connector providing unified access to denial reasons, "
        "policies, and evidence databases for utilization management workflows."
    )
    icon: str = "FileText"
    name: str = "AppealsDataConnector"
    category: str = "connectors"

    def __init__(self, **kwargs):
        """Initialize AppealsDataConnector with healthcare base inputs and appeals-specific inputs."""
        super().__init__(**kwargs)

        # Add appeals-specific inputs to the base class inputs
        appeals_inputs = [
            MessageTextInput(
                name="appeals_request",
                display_name="Appeals Data Request",
                info=(
                    "Appeals data request. Can be JSON string with appeal ID, member information, "
                    "or search criteria for denial reasons, policies, or evidence."
                ),
                value='{"appeal_id": "APP_20241011_001", "request_type": "denial_reasons"}',
            ),
            DropdownInput(
                name="data_source",
                display_name="Data Source",
                options=["denial_reasons", "policies", "evidence", "comprehensive"],
                value="comprehensive",
                info="Type of appeals data to access",
            ),
            DropdownInput(
                name="appeals_system",
                display_name="Appeals System",
                options=["change_healthcare", "optum", "internal", "mock"],
                value="mock",
                info="Appeals management system to connect to",
            ),
            StrInput(
                name="search_scope",
                display_name="Search Scope",
                value="relevant",
                info="Scope of data search (specific, relevant, comprehensive)",
                advanced=True,
            ),
            IntInput(
                name="max_results",
                display_name="Maximum Results",
                value=50,
                info="Maximum number of results to return",
                advanced=True,
            ),
            BoolInput(
                name="include_historical",
                display_name="Include Historical Data",
                value=True,
                info="Include historical denial reasons and policy data",
                advanced=True,
            ),
        ]

        # Combine base class inputs with appeals-specific inputs
        self.inputs = self.inputs + appeals_inputs

        # Set appeals-specific defaults
        self._request_id = None
        self.test_mode = True
        self.mock_mode = True

    outputs = [
        Output(
            display_name="Denial Reasons",
            name="denial_reasons",
            info="Denial reasons and decision documentation",
            method="get_denial_reasons",
        ),
        Output(
            display_name="Policy Data",
            name="policy_data",
            info="Relevant policies and coverage guidelines",
            method="search_policies",
        ),
        Output(
            display_name="Evidence Data",
            name="evidence_data",
            info="Clinical evidence and supporting documentation",
            method="get_evidence",
        ),
        Output(
            display_name="Comprehensive Data",
            name="comprehensive_data",
            info="All appeals-related data in structured format",
            method="get_comprehensive_data",
        ),
    ]

    def get_required_fields(self) -> List[str]:
        """Get required fields for appeals data access."""
        return ["appeal_id"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mock appeals data response for development and testing."""
        return self._get_mock_appeals_data(request_data)

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process real appeals data request."""
        # For now, return mock response with note about real integration
        response = self._get_mock_appeals_data(request_data)
        response["note"] = f"Mock response - {self.appeals_system} integration pending"
        return response

    def _parse_appeals_request(self, request: str) -> Dict[str, Any]:
        """Parse and validate appeals data request."""
        try:
            if isinstance(request, str):
                request_data = json.loads(request)
            else:
                request_data = request

            # Validate required fields based on request type
            required_fields = self.get_required_fields()
            for field in required_fields:
                if field not in request_data:
                    raise ValueError(f"Missing required field: {field}")

            return request_data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in appeals request: {e}") from e

    def _get_mock_appeals_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mock appeals data for development and testing."""
        appeal_id = request_data.get("appeal_id", "APP_20241011_001")
        request_type = request_data.get("request_type", "comprehensive")
        member_id = request_data.get("member_id", "MEM123456")

        return {
            "request_id": self._request_id or f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "appeal_id": appeal_id,
            "member_id": member_id,
            "data_source": self.data_source,
            "appeals_system": self.appeals_system,
            "denial_reasons": self._get_mock_denial_reasons(appeal_id),
            "policies": self._get_mock_policies(appeal_id),
            "evidence": self._get_mock_evidence(appeal_id),
            "processing_metadata": {
                "search_scope": self.search_scope,
                "max_results": self.max_results,
                "include_historical": self.include_historical,
                "response_time_ms": 187,
                "data_quality_score": 0.94,
            },
        }

    def _get_mock_denial_reasons(self, appeal_id: str) -> Dict[str, Any]:
        """Generate mock denial reasons data."""
        return {
            "denial_id": f"DENY_{appeal_id.split('_')[-1]}",
            "denial_date": "2024-10-01",
            "primary_reason": "Insufficient medical necessity documentation",
            "secondary_reasons": [
                "Lack of conservative treatment documentation",
                "Missing physician justification",
                "Incomplete symptom documentation"
            ],
            "denial_code": "MN001",
            "decision_criteria": {
                "policy_reference": "Policy_MRI_001",
                "clinical_guidelines": "ACR_Appropriateness_Criteria",
                "coverage_determination": "Prior_Authorization_Required"
            },
            "reviewer_information": {
                "reviewer_id": "REV001",
                "reviewer_type": "Clinical Pharmacist",
                "review_date": "2024-10-01",
                "review_duration_minutes": 25
            },
            "appeal_eligibility": {
                "appeal_allowed": True,
                "appeal_deadline": "2024-12-01",
                "appeal_levels": ["Internal Review", "External Review", "State Review"]
            }
        }

    def _get_mock_policies(self, appeal_id: str) -> Dict[str, Any]:
        """Generate mock policies data."""
        return {
            "relevant_policies": [
                {
                    "policy_id": "Policy_MRI_001",
                    "policy_name": "MRI Imaging Prior Authorization Policy",
                    "version": "2024.1",
                    "effective_date": "2024-01-01",
                    "policy_sections": [
                        {
                            "section": "Medical Necessity Criteria",
                            "requirements": [
                                "Failed conservative treatment for 6-8 weeks",
                                "Persistent symptoms affecting daily activities",
                                "Clinical exam findings supporting imaging need"
                            ]
                        },
                        {
                            "section": "Documentation Requirements",
                            "requirements": [
                                "Physician notes with clinical justification",
                                "Treatment history documentation",
                                "Symptom severity assessment"
                            ]
                        }
                    ],
                    "relevance_score": 0.92
                },
                {
                    "policy_id": "Policy_Conservative_Treatment_002",
                    "policy_name": "Conservative Treatment Requirements",
                    "version": "2024.1",
                    "effective_date": "2024-01-01",
                    "policy_sections": [
                        {
                            "section": "Required Treatments",
                            "requirements": [
                                "Physical therapy (minimum 4 sessions)",
                                "Anti-inflammatory medications",
                                "Activity modification"
                            ]
                        }
                    ],
                    "relevance_score": 0.85
                }
            ],
            "policy_matching_criteria": {
                "service_type": "diagnostic_imaging",
                "anatomical_area": "lumbar_spine",
                "clinical_indication": "chronic_pain"
            }
        }

    def _get_mock_evidence(self, appeal_id: str) -> Dict[str, Any]:
        """Generate mock evidence data."""
        return {
            "clinical_evidence": [
                {
                    "evidence_id": "EVID_001",
                    "evidence_type": "physician_notes",
                    "date": "2024-09-15",
                    "source": "Primary Care Provider",
                    "content_summary": "Patient reports persistent lower back pain, failed PT",
                    "relevance_score": 0.94,
                    "supporting_points": [
                        "6 weeks of physical therapy completed",
                        "Ongoing pain severity 7/10",
                        "Functional limitation documented"
                    ]
                },
                {
                    "evidence_id": "EVID_002",
                    "evidence_type": "treatment_history",
                    "date": "2024-08-01",
                    "source": "Physical Therapy Records",
                    "content_summary": "PT treatment log showing 6 sessions completed",
                    "relevance_score": 0.89,
                    "supporting_points": [
                        "All prescribed exercises completed",
                        "Minimal improvement noted",
                        "Therapist recommendation for imaging"
                    ]
                },
                {
                    "evidence_id": "EVID_003",
                    "evidence_type": "diagnostic_results",
                    "date": "2024-09-20",
                    "source": "Diagnostic Center",
                    "content_summary": "X-ray results showing mild degenerative changes",
                    "relevance_score": 0.82,
                    "supporting_points": [
                        "Mild disc space narrowing L4-L5",
                        "No acute fractures",
                        "Findings consistent with symptoms"
                    ]
                }
            ],
            "supporting_documentation": {
                "medical_records_count": 8,
                "imaging_studies_count": 2,
                "specialist_consultations": 1,
                "pharmacy_records": 3
            },
            "evidence_quality_assessment": {
                "completeness_score": 0.87,
                "consistency_score": 0.91,
                "timeliness_score": 0.94,
                "overall_quality": 0.91
            }
        }

    def get_denial_reasons(self) -> Data:
        """Get denial reasons and decision documentation."""
        try:
            request_data = self._parse_appeals_request(self.appeals_request)
            request_data["request_type"] = "denial_reasons"

            result = self.execute_healthcare_workflow(request_data)

            if result.data and not result.data.get("error"):
                denial_data = result.data.get("denial_reasons", {})
                self.status = f"Denial Reasons Retrieved: {denial_data.get('denial_id', 'Unknown')}"
            else:
                self.status = "Denial Reasons Retrieval Failed"

            return result

        except Exception as e:
            return self._handle_healthcare_error(e, "denial_reasons_retrieval")

    def search_policies(self) -> Data:
        """Search and retrieve relevant policies."""
        try:
            request_data = self._parse_appeals_request(self.appeals_request)
            request_data["request_type"] = "policies"

            # Override get_mock_response temporarily for policy search
            original_get_mock = self.get_mock_response
            self.get_mock_response = lambda data: {"policies": self._get_mock_policies(data.get("appeal_id", ""))}

            result = self.execute_healthcare_workflow(request_data)

            # Restore original method
            self.get_mock_response = original_get_mock

            if result.data and not result.data.get("error"):
                policies = result.data.get("policies", {}).get("relevant_policies", [])
                self.status = f"Policies Retrieved: {len(policies)} policies found"
            else:
                self.status = "Policy Search Failed"

            return result

        except Exception as e:
            return self._handle_healthcare_error(e, "policy_search")

    def get_evidence(self) -> Data:
        """Get clinical evidence and supporting documentation."""
        try:
            request_data = self._parse_appeals_request(self.appeals_request)
            request_data["request_type"] = "evidence"

            # Override get_mock_response temporarily for evidence retrieval
            original_get_mock = self.get_mock_response
            self.get_mock_response = lambda data: {"evidence": self._get_mock_evidence(data.get("appeal_id", ""))}

            result = self.execute_healthcare_workflow(request_data)

            # Restore original method
            self.get_mock_response = original_get_mock

            if result.data and not result.data.get("error"):
                evidence = result.data.get("evidence", {}).get("clinical_evidence", [])
                self.status = f"Evidence Retrieved: {len(evidence)} pieces of evidence"
            else:
                self.status = "Evidence Retrieval Failed"

            return result

        except Exception as e:
            return self._handle_healthcare_error(e, "evidence_retrieval")

    def get_comprehensive_data(self) -> Data:
        """Get comprehensive appeals data including all sources."""
        try:
            request_data = self._parse_appeals_request(self.appeals_request)
            request_data["request_type"] = "comprehensive"

            result = self.execute_healthcare_workflow(request_data)

            if result.data and not result.data.get("error"):
                self.status = f"Comprehensive Data Retrieved for Appeal {request_data.get('appeal_id', 'Unknown')}"
            else:
                self.status = "Comprehensive Data Retrieval Failed"

            return result

        except Exception as e:
            return self._handle_healthcare_error(e, "comprehensive_data_retrieval")