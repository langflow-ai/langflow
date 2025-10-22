"""Provider Network Connector for healthcare provider directory and network operations."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langflow.base.healthcare_connector_base import HealthcareConnectorBase
from langflow.io import (
    BoolInput,
    DropdownInput,
    MessageTextInput,
    StrInput,
)
from langflow.schema.data import Data


class ProviderNetworkConnector(HealthcareConnectorBase):
    """
    HIPAA-compliant Provider Network Connector for healthcare provider
    directory operations, network adequacy analysis, and provider data management.

    Supports provider searches, network analysis, credentialing status,
    and provider-plan relationship management.
    """

    display_name: str = "Provider Network Connector"
    description: str = "Access provider directories, network adequacy data, and provider relationship management"
    icon: str = "Users"
    name: str = "ProviderNetworkConnector"

    inputs = HealthcareConnectorBase.inputs + [
        StrInput(
            name="provider_npi",
            display_name="Provider NPI",
            placeholder="1234567890",
            info="National Provider Identifier for specific provider lookup",
            tool_mode=True,
        ),
        StrInput(
            name="provider_name",
            display_name="Provider Name",
            placeholder="Dr. Smith",
            info="Provider name for search (last name or full name)",
            tool_mode=True,
        ),
        DropdownInput(
            name="provider_type",
            display_name="Provider Type",
            options=[
                "primary_care",
                "specialist",
                "hospital",
                "facility",
                "mental_health",
                "pharmacy",
                "ancillary",
                "all_types"
            ],
            value="all_types",
            info="Type of healthcare provider to search for",
            tool_mode=True,
        ),
        DropdownInput(
            name="specialty",
            display_name="Medical Specialty",
            options=[
                "family_medicine",
                "internal_medicine",
                "pediatrics",
                "cardiology",
                "endocrinology",
                "neurology",
                "orthopedics",
                "dermatology",
                "psychiatry",
                "emergency_medicine",
                "all_specialties"
            ],
            value="all_specialties",
            info="Medical specialty for provider filtering",
            tool_mode=True,
        ),
        StrInput(
            name="geographic_area",
            display_name="Geographic Area",
            placeholder="90210, Los Angeles, CA",
            info="ZIP code, city, or state for geographic filtering",
            tool_mode=True,
        ),
        DropdownInput(
            name="network_status",
            display_name="Network Status",
            options=[
                "active",
                "inactive",
                "pending",
                "terminated",
                "all_statuses"
            ],
            value="active",
            info="Provider network participation status",
            tool_mode=True,
        ),
        BoolInput(
            name="include_locations",
            display_name="Include Locations",
            value=True,
            info="Include provider practice locations in results",
            tool_mode=True,
        ),
        BoolInput(
            name="include_credentials",
            display_name="Include Credentials",
            value=True,
            info="Include credentialing and certification information",
            tool_mode=True,
        ),
        BoolInput(
            name="include_quality_metrics",
            display_name="Include Quality Metrics",
            value=False,
            info="Include provider quality scores and performance metrics",
            tool_mode=True,
        ),
        DropdownInput(
            name="search_radius_miles",
            display_name="Search Radius (Miles)",
            options=["5", "10", "25", "50", "100", "unlimited"],
            value="25",
            info="Geographic search radius from specified location",
            tool_mode=True,
        ),
    ]

    def get_required_fields(self) -> List[str]:
        """Required fields for provider network requests."""
        return []  # Flexible search - can search by any combination

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mock provider network data."""
        provider_type = request_data.get("provider_type", "all_types")
        specialty = request_data.get("specialty", "all_specialties")
        network_status = request_data.get("network_status", "active")
        geographic_area = request_data.get("geographic_area", "")

        # Mock provider data
        mock_providers = [
            {
                "npi": "1234567890",
                "provider_name": "Dr. Sarah Johnson, MD",
                "first_name": "Sarah",
                "last_name": "Johnson",
                "credentials": "MD",
                "provider_type": "primary_care",
                "primary_specialty": "family_medicine",
                "secondary_specialties": ["preventive_medicine"],
                "network_status": "active",
                "contract_start_date": "2020-01-15",
                "contract_end_date": "2025-12-31",
                "accepting_new_patients": True,
                "board_certified": True,
                "languages_spoken": ["English", "Spanish"],
                "practice_locations": [
                    {
                        "location_id": "LOC001",
                        "practice_name": "Community Health Center",
                        "address": {
                            "street": "123 Main Street",
                            "city": "Los Angeles",
                            "state": "CA",
                            "zip_code": "90210",
                            "county": "Los Angeles"
                        },
                        "phone": "(555) 123-4567",
                        "fax": "(555) 123-4568",
                        "office_hours": {
                            "monday": "8:00 AM - 5:00 PM",
                            "tuesday": "8:00 AM - 5:00 PM",
                            "wednesday": "8:00 AM - 5:00 PM",
                            "thursday": "8:00 AM - 5:00 PM",
                            "friday": "8:00 AM - 4:00 PM"
                        },
                        "accessibility_features": ["wheelchair_accessible", "parking_available"]
                    }
                ],
                "credentialing_info": {
                    "credentialing_status": "active",
                    "last_credentialing_date": "2023-01-15",
                    "next_recredentialing_date": "2026-01-15",
                    "malpractice_insurance": "current",
                    "dea_registration": "active",
                    "state_license": {
                        "license_number": "CA12345",
                        "expiration_date": "2024-12-31",
                        "status": "active"
                    }
                },
                "quality_metrics": {
                    "overall_quality_score": 4.2,
                    "patient_satisfaction": 4.5,
                    "clinical_quality": 4.0,
                    "efficiency_metrics": 3.8,
                    "hedis_performance": {
                        "diabetes_care": 85.2,
                        "preventive_care": 78.9
                    }
                },
                "network_adequacy": {
                    "distance_to_members": "2.3 miles average",
                    "appointment_availability": "within_14_days",
                    "coverage_area": "primary"
                }
            },
            {
                "npi": "2345678901",
                "provider_name": "Dr. Michael Chen, MD",
                "first_name": "Michael",
                "last_name": "Chen",
                "credentials": "MD, FACC",
                "provider_type": "specialist",
                "primary_specialty": "cardiology",
                "secondary_specialties": ["interventional_cardiology"],
                "network_status": "active",
                "contract_start_date": "2019-06-01",
                "contract_end_date": "2024-05-31",
                "accepting_new_patients": True,
                "board_certified": True,
                "languages_spoken": ["English", "Mandarin"],
                "practice_locations": [
                    {
                        "location_id": "LOC002",
                        "practice_name": "Heart & Vascular Institute",
                        "address": {
                            "street": "456 Medical Drive",
                            "city": "Beverly Hills",
                            "state": "CA",
                            "zip_code": "90212",
                            "county": "Los Angeles"
                        },
                        "phone": "(555) 234-5678",
                        "fax": "(555) 234-5679",
                        "office_hours": {
                            "monday": "7:00 AM - 6:00 PM",
                            "tuesday": "7:00 AM - 6:00 PM",
                            "wednesday": "7:00 AM - 6:00 PM",
                            "thursday": "7:00 AM - 6:00 PM",
                            "friday": "7:00 AM - 5:00 PM"
                        },
                        "accessibility_features": ["wheelchair_accessible", "valet_parking"]
                    }
                ],
                "credentialing_info": {
                    "credentialing_status": "active",
                    "last_credentialing_date": "2023-06-01",
                    "next_recredentialing_date": "2026-06-01",
                    "malpractice_insurance": "current",
                    "dea_registration": "active",
                    "state_license": {
                        "license_number": "CA67890",
                        "expiration_date": "2025-06-30",
                        "status": "active"
                    }
                },
                "quality_metrics": {
                    "overall_quality_score": 4.7,
                    "patient_satisfaction": 4.6,
                    "clinical_quality": 4.8,
                    "efficiency_metrics": 4.5,
                    "specialty_metrics": {
                        "cardiac_outcomes": 92.3,
                        "readmission_rate": 3.2
                    }
                },
                "network_adequacy": {
                    "distance_to_members": "5.1 miles average",
                    "appointment_availability": "within_21_days",
                    "coverage_area": "secondary"
                }
            }
        ]

        # Filter providers based on search criteria
        filtered_providers = []
        for provider in mock_providers:
            if (provider_type == "all_types" or provider["provider_type"] == provider_type) and \
               (specialty == "all_specialties" or provider["primary_specialty"] == specialty) and \
               (network_status == "all_statuses" or provider["network_status"] == network_status):
                filtered_providers.append(provider)

        # Remove sensitive data if not requested
        if not request_data.get("include_locations", True):
            for provider in filtered_providers:
                provider.pop("practice_locations", None)

        if not request_data.get("include_credentials", True):
            for provider in filtered_providers:
                provider.pop("credentialing_info", None)

        if not request_data.get("include_quality_metrics", False):
            for provider in filtered_providers:
                provider.pop("quality_metrics", None)

        mock_data = {
            "status": "success",
            "search_criteria": {
                "provider_type": provider_type,
                "specialty": specialty,
                "network_status": network_status,
                "geographic_area": geographic_area,
                "search_radius": request_data.get("search_radius_miles", "25")
            },
            "total_providers": len(filtered_providers),
            "providers": filtered_providers,
            "network_adequacy_summary": {
                "provider_density": "adequate",
                "geographic_coverage": "92%",
                "appointment_availability": "meets_standards",
                "specialty_coverage": {
                    "primary_care": "adequate",
                    "specialist": "adequate",
                    "mental_health": "limited"
                }
            },
            "search_performance": {
                "search_time_ms": 156,
                "data_freshness": "last_updated_24_hours"
            }
        }

        return mock_data

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process provider network request with healthcare-specific logic."""
        # Log PHI access for audit trail
        self._log_phi_access("provider_network_access", ["provider_data", "practice_locations"])

        # Validate search criteria - at least one search parameter should be provided
        search_params = [
            request_data.get("provider_npi"),
            request_data.get("provider_name"),
            request_data.get("geographic_area")
        ]

        if not any(param and param.strip() for param in search_params):
            # Allow searches by type/specialty only
            if request_data.get("provider_type") == "all_types" and request_data.get("specialty") == "all_specialties":
                # This would return too many results in production, but allow for demo
                pass

        # In production, this would connect to actual provider directory services
        # For now, return comprehensive mock data
        return self.get_mock_response(request_data)

    def run(
        self,
        provider_npi: str = "",
        provider_name: str = "",
        provider_type: str = "all_types",
        specialty: str = "all_specialties",
        geographic_area: str = "",
        network_status: str = "active",
        include_locations: bool = True,
        include_credentials: bool = True,
        include_quality_metrics: bool = False,
        search_radius_miles: str = "25",
        **kwargs
    ) -> Data:
        """
        Execute provider network directory search workflow.

        Args:
            provider_npi: National Provider Identifier for specific lookup
            provider_name: Provider name for search
            provider_type: Type of healthcare provider
            specialty: Medical specialty for filtering
            geographic_area: Geographic search area
            network_status: Provider network participation status
            include_locations: Include practice locations
            include_credentials: Include credentialing information
            include_quality_metrics: Include quality performance metrics
            search_radius_miles: Geographic search radius

        Returns:
            Data: Provider network search response with healthcare metadata
        """
        request_data = {
            "provider_npi": provider_npi,
            "provider_name": provider_name,
            "provider_type": provider_type,
            "specialty": specialty,
            "geographic_area": geographic_area,
            "network_status": network_status,
            "include_locations": include_locations,
            "include_credentials": include_credentials,
            "include_quality_metrics": include_quality_metrics,
            "search_radius_miles": search_radius_miles,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self.execute_healthcare_workflow(request_data)