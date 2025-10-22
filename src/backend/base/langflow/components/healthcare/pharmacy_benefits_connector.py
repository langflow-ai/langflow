"""Pharmacy Benefits Connector for PBM and formulary data integration."""

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


class PharmacyBenefitsConnector(HealthcareConnectorBase):
    """
    HIPAA-compliant Pharmacy Benefits Connector for PBM operations,
    formulary management, and pharmacy benefit administration.

    Supports formulary lookups, prior authorization management,
    drug utilization analysis, and pharmacy network operations.
    """

    display_name: str = "Pharmacy Benefits Connector"
    description: str = "Access PBM data, formulary information, and pharmacy benefit management systems"
    icon: str = "Pill"
    name: str = "PharmacyBenefitsConnector"

    inputs = HealthcareConnectorBase.inputs + [
        StrInput(
            name="drug_name",
            display_name="Drug Name",
            placeholder="metformin, lisinopril, etc.",
            info="Brand or generic drug name for formulary lookup",
            tool_mode=True,
        ),
        StrInput(
            name="ndc_number",
            display_name="NDC Number",
            placeholder="12345-678-90",
            info="National Drug Code for specific drug identification",
            tool_mode=True,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=[
                "formulary_lookup",
                "prior_authorization",
                "drug_utilization",
                "pharmacy_network",
                "cost_analysis",
                "clinical_review"
            ],
            value="formulary_lookup",
            info="Type of pharmacy benefits search to perform",
            tool_mode=True,
        ),
        DropdownInput(
            name="formulary_tier",
            display_name="Formulary Tier",
            options=[
                "tier_1_generic",
                "tier_2_preferred_brand",
                "tier_3_non_preferred_brand",
                "tier_4_specialty",
                "tier_5_lifestyle",
                "all_tiers"
            ],
            value="all_tiers",
            info="Formulary tier for drug classification",
            tool_mode=True,
        ),
        DropdownInput(
            name="therapeutic_class",
            display_name="Therapeutic Class",
            options=[
                "diabetes_medications",
                "cardiovascular_medications",
                "respiratory_medications",
                "pain_management",
                "mental_health",
                "oncology",
                "immunology",
                "all_classes"
            ],
            value="all_classes",
            info="Therapeutic class for drug categorization",
            tool_mode=True,
        ),
        StrInput(
            name="member_id",
            display_name="Member ID",
            placeholder="M123456789",
            info="Member identifier for personalized benefit information",
            tool_mode=True,
        ),
        BoolInput(
            name="include_alternatives",
            display_name="Include Alternatives",
            value=True,
            info="Include therapeutic alternatives and generic options",
            tool_mode=True,
        ),
        BoolInput(
            name="include_cost_sharing",
            display_name="Include Cost Sharing",
            value=True,
            info="Include copay, coinsurance, and deductible information",
            tool_mode=True,
        ),
        BoolInput(
            name="include_restrictions",
            display_name="Include Restrictions",
            value=True,
            info="Include prior authorization and quantity limit restrictions",
            tool_mode=True,
        ),
        BoolInput(
            name="include_utilization",
            display_name="Include Utilization",
            value=False,
            info="Include drug utilization patterns and trends",
            tool_mode=True,
        ),
        DropdownInput(
            name="pharmacy_type",
            display_name="Pharmacy Type",
            options=[
                "retail_pharmacy",
                "mail_order",
                "specialty_pharmacy",
                "hospital_pharmacy",
                "all_types"
            ],
            value="all_types",
            info="Type of pharmacy for network and pricing information",
            tool_mode=True,
        ),
    ]

    def get_required_fields(self) -> List[str]:
        """Required fields for pharmacy benefits requests."""
        return ["search_type"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mock pharmacy benefits data."""
        search_type = request_data.get("search_type", "formulary_lookup")
        drug_name = request_data.get("drug_name", "")
        formulary_tier = request_data.get("formulary_tier", "all_tiers")

        # Mock formulary data
        formulary_drugs = [
            {
                "drug_name": "Metformin",
                "generic_name": "metformin hydrochloride",
                "brand_names": ["Glucophage", "Fortamet", "Glumetza"],
                "ndc_numbers": ["12345-678-90", "98765-432-10"],
                "formulary_status": "covered",
                "formulary_tier": "tier_1_generic",
                "therapeutic_class": "diabetes_medications",
                "drug_class": "biguanides",
                "strength_forms": [
                    {"strength": "500mg", "form": "tablet", "ndc": "12345-678-90"},
                    {"strength": "850mg", "form": "tablet", "ndc": "12345-678-91"},
                    {"strength": "1000mg", "form": "tablet", "ndc": "12345-678-92"}
                ],
                "cost_sharing": {
                    "retail_copay": "$5",
                    "mail_order_copay": "$10",
                    "specialty_copay": "N/A",
                    "coinsurance": "0%",
                    "deductible_applies": False
                },
                "restrictions": {
                    "prior_authorization": False,
                    "step_therapy": False,
                    "quantity_limits": "90 tablets per 30 days",
                    "age_restrictions": "None",
                    "gender_restrictions": "None"
                },
                "alternatives": [
                    {
                        "drug_name": "Glipizide",
                        "reason": "Alternative diabetes medication",
                        "tier": "tier_1_generic",
                        "cost_difference": "$0"
                    }
                ],
                "clinical_information": {
                    "indication": "Type 2 diabetes mellitus",
                    "contraindications": ["Severe renal impairment", "Metabolic acidosis"],
                    "black_box_warnings": [],
                    "monitoring_requirements": ["Renal function", "Vitamin B12 levels"]
                }
            },
            {
                "drug_name": "Humira",
                "generic_name": "adalimumab",
                "brand_names": ["Humira"],
                "ndc_numbers": ["55555-123-45"],
                "formulary_status": "covered_with_restrictions",
                "formulary_tier": "tier_4_specialty",
                "therapeutic_class": "immunology",
                "drug_class": "TNF blockers",
                "strength_forms": [
                    {"strength": "40mg/0.8mL", "form": "pen injector", "ndc": "55555-123-45"}
                ],
                "cost_sharing": {
                    "retail_copay": "N/A",
                    "mail_order_copay": "N/A",
                    "specialty_copay": "$50",
                    "coinsurance": "20%",
                    "deductible_applies": True
                },
                "restrictions": {
                    "prior_authorization": True,
                    "step_therapy": True,
                    "quantity_limits": "2 pens per 28 days",
                    "specialty_pharmacy_required": True,
                    "clinical_criteria": ["Failed conventional DMARDs", "Active disease"]
                },
                "alternatives": [
                    {
                        "drug_name": "Enbrel (etanercept)",
                        "reason": "Alternative TNF blocker",
                        "tier": "tier_4_specialty",
                        "cost_difference": "Similar"
                    }
                ],
                "clinical_information": {
                    "indication": "Rheumatoid arthritis, Crohn's disease, psoriasis",
                    "contraindications": ["Active infections", "Live vaccines"],
                    "black_box_warnings": ["Increased infection risk", "Malignancy risk"],
                    "monitoring_requirements": ["CBC", "Liver function", "TB screening"]
                }
            }
        ]

        # Mock prior authorization data
        prior_auth_data = {
            "drug_name": drug_name or "Humira",
            "pa_status": "required",
            "criteria": [
                "Diagnosis of rheumatoid arthritis or similar autoimmune condition",
                "Failure of at least 2 conventional DMARDs",
                "Active disease despite conventional therapy",
                "No contraindications to TNF blockers"
            ],
            "required_documentation": [
                "Medical records documenting diagnosis",
                "Previous medication trial documentation",
                "Current disease activity assessments",
                "Laboratory results (CBC, liver function, TB screening)"
            ],
            "approval_timeframe": "72 hours for urgent requests, 5 business days standard",
            "duration_of_approval": "6 months with renewal option",
            "appeal_process": "Available within 60 days of denial"
        }

        # Mock utilization data
        utilization_data = {
            "drug_name": drug_name or "Metformin",
            "total_members_using": 12450,
            "monthly_claims": 8750,
            "average_days_supply": 30,
            "adherence_rate": 78.5,
            "cost_trends": {
                "average_claim_cost": "$25.50",
                "trend_vs_prior_year": "+2.3%",
                "generic_substitution_rate": "94.2%"
            },
            "utilization_patterns": {
                "peak_months": ["January", "February"],
                "seasonal_variations": "Higher utilization in winter months",
                "age_demographics": {
                    "18-34": "15%",
                    "35-54": "35%",
                    "55-64": "30%",
                    "65+": "20%"
                }
            }
        }

        # Mock pharmacy network data
        pharmacy_network = {
            "network_pharmacies": [
                {
                    "pharmacy_name": "CVS Pharmacy",
                    "pharmacy_type": "retail_pharmacy",
                    "npi": "1234567890",
                    "address": "123 Main St, Los Angeles, CA 90210",
                    "phone": "(555) 123-4567",
                    "hours": "Mon-Fri 9AM-9PM, Sat-Sun 9AM-6PM",
                    "services": ["prescription_filling", "immunizations", "medication_counseling"],
                    "specialty_services": False
                },
                {
                    "pharmacy_name": "Specialty Pharmacy Plus",
                    "pharmacy_type": "specialty_pharmacy",
                    "npi": "2345678901",
                    "address": "456 Medical Dr, Beverly Hills, CA 90212",
                    "phone": "(555) 234-5678",
                    "hours": "Mon-Fri 8AM-6PM",
                    "services": ["specialty_medications", "patient_support", "clinical_monitoring"],
                    "specialty_services": True,
                    "therapeutic_areas": ["oncology", "immunology", "rare_diseases"]
                }
            ],
            "network_adequacy": {
                "retail_coverage": "98.5%",
                "specialty_coverage": "95.2%",
                "mail_order_availability": "100%",
                "average_distance": "2.3 miles"
            }
        }

        # Build response based on search type
        mock_data = {
            "status": "success",
            "search_type": search_type,
            "query_parameters": {
                "drug_name": drug_name,
                "formulary_tier": formulary_tier,
                "therapeutic_class": request_data.get("therapeutic_class", "all_classes"),
                "member_id": request_data.get("member_id", "")
            },
            "data_source": "PBM Database",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if search_type == "formulary_lookup":
            # Filter drugs if specific drug name provided
            if drug_name:
                matching_drugs = [d for d in formulary_drugs if
                                drug_name.lower() in d["drug_name"].lower() or
                                drug_name.lower() in d["generic_name"].lower()]
                mock_data["formulary_results"] = matching_drugs if matching_drugs else formulary_drugs[:1]
            else:
                mock_data["formulary_results"] = formulary_drugs

        elif search_type == "prior_authorization":
            mock_data["prior_authorization"] = prior_auth_data

        elif search_type == "drug_utilization":
            mock_data["utilization_analysis"] = utilization_data

        elif search_type == "pharmacy_network":
            mock_data["pharmacy_network"] = pharmacy_network

        elif search_type == "cost_analysis":
            mock_data["cost_analysis"] = {
                "drug_costs": {
                    "tier_1_avg": "$8.50",
                    "tier_2_avg": "$35.75",
                    "tier_3_avg": "$75.25",
                    "tier_4_avg": "$425.00"
                },
                "member_cost_sharing": {
                    "average_copay": "$15.25",
                    "average_coinsurance": "15%",
                    "deductible_impact": "35% of members"
                },
                "plan_costs": {
                    "total_drug_spend": "$12,450,000",
                    "per_member_per_month": "$125.50",
                    "generic_savings": "$2,300,000"
                }
            }

        # Add alternatives if requested
        if request_data.get("include_alternatives", True) and search_type == "formulary_lookup":
            for drug in mock_data.get("formulary_results", []):
                if "alternatives" not in drug:
                    drug["alternatives"] = [
                        {
                            "drug_name": "Generic Alternative",
                            "reason": "Lower cost option",
                            "tier": "tier_1_generic",
                            "cost_difference": "-$20"
                        }
                    ]

        return mock_data

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process pharmacy benefits request with healthcare-specific logic."""
        # Log PHI access for audit trail
        phi_elements = ["member_benefits", "drug_utilization"]
        if request_data.get("member_id"):
            phi_elements.append("member_id")

        self._log_phi_access("pharmacy_benefits_access", phi_elements)

        # Validate search type
        valid_types = [
            "formulary_lookup", "prior_authorization", "drug_utilization",
            "pharmacy_network", "cost_analysis", "clinical_review"
        ]

        search_type = request_data.get("search_type")
        if search_type not in valid_types:
            raise ValueError(f"Invalid search type. Must be one of: {valid_types}")

        # Validate drug identifiers if provided
        drug_name = request_data.get("drug_name", "")
        ndc_number = request_data.get("ndc_number", "")

        if search_type in ["formulary_lookup", "prior_authorization", "clinical_review"]:
            if not drug_name and not ndc_number:
                # Allow for general searches, but warn about broad results
                pass

        # In production, this would connect to actual PBM systems
        # For now, return comprehensive mock data
        return self.get_mock_response(request_data)

    def run(
        self,
        drug_name: str = "",
        ndc_number: str = "",
        search_type: str = "formulary_lookup",
        formulary_tier: str = "all_tiers",
        therapeutic_class: str = "all_classes",
        member_id: str = "",
        include_alternatives: bool = True,
        include_cost_sharing: bool = True,
        include_restrictions: bool = True,
        include_utilization: bool = False,
        pharmacy_type: str = "all_types",
        **kwargs
    ) -> Data:
        """
        Execute pharmacy benefits workflow.

        Args:
            drug_name: Brand or generic drug name
            ndc_number: National Drug Code
            search_type: Type of pharmacy benefits search
            formulary_tier: Formulary tier classification
            therapeutic_class: Therapeutic drug class
            member_id: Member identifier for personalized benefits
            include_alternatives: Include therapeutic alternatives
            include_cost_sharing: Include cost sharing information
            include_restrictions: Include coverage restrictions
            include_utilization: Include utilization patterns
            pharmacy_type: Type of pharmacy for network information

        Returns:
            Data: Pharmacy benefits response with healthcare metadata
        """
        request_data = {
            "drug_name": drug_name,
            "ndc_number": ndc_number,
            "search_type": search_type,
            "formulary_tier": formulary_tier,
            "therapeutic_class": therapeutic_class,
            "member_id": member_id,
            "include_alternatives": include_alternatives,
            "include_cost_sharing": include_cost_sharing,
            "include_restrictions": include_restrictions,
            "include_utilization": include_utilization,
            "pharmacy_type": pharmacy_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self.execute_healthcare_workflow(request_data)