"""Medical Terminology Connector for healthcare terminology validation and standardization."""

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


class MedicalTerminologyConnector(HealthcareConnectorBase):
    """
    HIPAA-compliant Medical Terminology Connector for healthcare terminology
    validation, standardization, and medical coding integration.

    Supports ICD-10, CPT, SNOMED CT, LOINC, and other medical code systems
    with validation, mapping, and terminology services.
    """

    display_name: str = "Medical Terminology Connector"
    description: str = "Validate and standardize medical terminology with ICD-10, CPT, SNOMED CT, and LOINC integration"
    icon: str = "BookOpen"
    name: str = "MedicalTerminologyConnector"

    inputs = HealthcareConnectorBase.inputs + [
        StrInput(
            name="medical_term",
            display_name="Medical Term",
            placeholder="diabetes mellitus, myocardial infarction, etc.",
            info="Medical term or description to validate or code",
            tool_mode=True,
        ),
        StrInput(
            name="medical_code",
            display_name="Medical Code",
            placeholder="E11.9, 99213, 73761003, etc.",
            info="Medical code to validate or lookup (ICD-10, CPT, SNOMED, etc.)",
            tool_mode=True,
        ),
        DropdownInput(
            name="terminology_system",
            display_name="Terminology System",
            options=[
                "icd_10_cm",
                "icd_10_pcs",
                "cpt",
                "hcpcs",
                "snomed_ct",
                "loinc",
                "rxnorm",
                "ndc",
                "all_systems"
            ],
            value="all_systems",
            info="Medical terminology or coding system to use",
            tool_mode=True,
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=[
                "exact_match",
                "fuzzy_search",
                "code_lookup",
                "term_validation",
                "code_mapping",
                "hierarchy_search"
            ],
            value="fuzzy_search",
            info="Type of terminology search to perform",
            tool_mode=True,
        ),
        BoolInput(
            name="include_synonyms",
            display_name="Include Synonyms",
            value=True,
            info="Include synonyms and alternative terms in results",
            tool_mode=True,
        ),
        BoolInput(
            name="include_hierarchy",
            display_name="Include Hierarchy",
            value=True,
            info="Include parent/child relationships and hierarchical information",
            tool_mode=True,
        ),
        BoolInput(
            name="include_mappings",
            display_name="Include Mappings",
            value=True,
            info="Include cross-terminology mappings (e.g., ICD-10 to SNOMED)",
            tool_mode=True,
        ),
        BoolInput(
            name="validate_active_only",
            display_name="Active Codes Only",
            value=True,
            info="Return only currently active/valid medical codes",
            tool_mode=True,
        ),
        DropdownInput(
            name="confidence_threshold",
            display_name="Confidence Threshold",
            options=["0.7", "0.8", "0.85", "0.9", "0.95"],
            value="0.8",
            info="Minimum confidence score for term matching",
            tool_mode=True,
        ),
        DropdownInput(
            name="max_results",
            display_name="Max Results",
            options=["5", "10", "20", "50", "100"],
            value="10",
            info="Maximum number of results to return",
            tool_mode=True,
        ),
    ]

    def get_required_fields(self) -> List[str]:
        """Required fields for medical terminology requests."""
        return ["search_type"]

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive mock medical terminology data."""
        medical_term = request_data.get("medical_term", "")
        medical_code = request_data.get("medical_code", "")
        terminology_system = request_data.get("terminology_system", "all_systems")
        search_type = request_data.get("search_type", "fuzzy_search")

        # Mock ICD-10 data
        icd10_results = [
            {
                "code": "E11.9",
                "description": "Type 2 diabetes mellitus without complications",
                "system": "icd_10_cm",
                "category": "Endocrine, nutritional and metabolic diseases",
                "parent_code": "E11",
                "parent_description": "Type 2 diabetes mellitus",
                "confidence": 0.95,
                "status": "active",
                "effective_date": "2023-10-01",
                "synonyms": [
                    "Type II diabetes mellitus",
                    "Adult-onset diabetes",
                    "Non-insulin-dependent diabetes mellitus",
                    "NIDDM"
                ],
                "hierarchy": {
                    "chapter": "E00-E89 Endocrine, nutritional and metabolic diseases",
                    "block": "E08-E13 Diabetes mellitus",
                    "category": "E11 Type 2 diabetes mellitus"
                },
                "clinical_information": {
                    "definition": "A form of diabetes mellitus characterized by insulin resistance and relative insulin deficiency",
                    "includes": ["Adult-onset diabetes", "Maturity-onset diabetes"],
                    "excludes": ["Type 1 diabetes mellitus (E10.-)", "Gestational diabetes (O24.4-)"]
                }
            },
            {
                "code": "E11.65",
                "description": "Type 2 diabetes mellitus with hyperglycemia",
                "system": "icd_10_cm",
                "category": "Endocrine, nutritional and metabolic diseases",
                "parent_code": "E11",
                "parent_description": "Type 2 diabetes mellitus",
                "confidence": 0.88,
                "status": "active",
                "effective_date": "2023-10-01",
                "synonyms": [
                    "Type 2 diabetes with high blood sugar",
                    "T2DM with hyperglycemia"
                ],
                "hierarchy": {
                    "chapter": "E00-E89 Endocrine, nutritional and metabolic diseases",
                    "block": "E08-E13 Diabetes mellitus",
                    "category": "E11 Type 2 diabetes mellitus"
                }
            }
        ]

        # Mock CPT data
        cpt_results = [
            {
                "code": "99213",
                "description": "Office or other outpatient visit for the evaluation and management of an established patient",
                "system": "cpt",
                "category": "Evaluation and Management",
                "confidence": 0.92,
                "status": "active",
                "effective_date": "2024-01-01",
                "work_rvu": 1.3,
                "practice_expense_rvu": 1.22,
                "malpractice_rvu": 0.07,
                "total_rvu": 2.59,
                "global_period": "XXX",
                "clinical_criteria": {
                    "key_components": [
                        "Problem focused history",
                        "Problem focused examination",
                        "Medical decision making of low complexity"
                    ],
                    "typical_time": "15 minutes",
                    "setting": "Office or other outpatient"
                }
            }
        ]

        # Mock SNOMED CT data
        snomed_results = [
            {
                "code": "44054006",
                "description": "Diabetes mellitus type 2",
                "system": "snomed_ct",
                "confidence": 0.97,
                "status": "active",
                "definition_status": "Primitive",
                "module": "900000000000207008",
                "synonyms": [
                    "Type 2 diabetes mellitus",
                    "Adult onset diabetes mellitus",
                    "Maturity onset diabetes"
                ],
                "relationships": {
                    "is_a": ["73211009|Diabetes mellitus"],
                    "finding_site": ["113331007|Endocrine system structure"],
                    "associated_morphology": ["46635009|Morphologic abnormality"]
                },
                "mappings": {
                    "icd_10_cm": ["E11.9", "E11"],
                    "mesh": ["D003924"]
                }
            }
        ]

        # Mock LOINC data
        loinc_results = [
            {
                "code": "4548-4",
                "description": "Hemoglobin A1c/Hemoglobin.total in Blood",
                "system": "loinc",
                "confidence": 0.94,
                "status": "active",
                "component": "Hemoglobin A1c/Hemoglobin.total",
                "property": "MFr",
                "time_aspect": "Pt",
                "system_class": "Bld",
                "scale": "Qn",
                "method": "",
                "short_name": "HbA1c MFr Bld",
                "example_units": "%",
                "reference_ranges": {
                    "normal": "< 5.7%",
                    "prediabetes": "5.7% - 6.4%",
                    "diabetes": ">= 6.5%"
                }
            }
        ]

        # Build response based on terminology system and search type
        mock_data = {
            "status": "success",
            "search_type": search_type,
            "terminology_system": terminology_system,
            "query": {
                "medical_term": medical_term,
                "medical_code": medical_code,
                "confidence_threshold": float(request_data.get("confidence_threshold", "0.8"))
            },
            "total_results": 0,
            "results": []
        }

        # Add results based on terminology system
        if terminology_system in ["icd_10_cm", "all_systems"]:
            mock_data["results"].extend(icd10_results)

        if terminology_system in ["cpt", "all_systems"]:
            mock_data["results"].extend(cpt_results)

        if terminology_system in ["snomed_ct", "all_systems"]:
            mock_data["results"].extend(snomed_results)

        if terminology_system in ["loinc", "all_systems"]:
            mock_data["results"].extend(loinc_results)

        # Filter results based on search criteria
        if medical_term:
            # Simulate term-based filtering
            term_lower = medical_term.lower()
            filtered_results = []
            for result in mock_data["results"]:
                if (term_lower in result["description"].lower() or
                    any(term_lower in syn.lower() for syn in result.get("synonyms", []))):
                    filtered_results.append(result)
            mock_data["results"] = filtered_results

        if medical_code:
            # Simulate code-based filtering
            filtered_results = [r for r in mock_data["results"] if r["code"] == medical_code]
            mock_data["results"] = filtered_results

        # Apply confidence threshold
        confidence_threshold = float(request_data.get("confidence_threshold", "0.8"))
        mock_data["results"] = [r for r in mock_data["results"]
                               if r.get("confidence", 1.0) >= confidence_threshold]

        # Limit results
        max_results = int(request_data.get("max_results", "10"))
        mock_data["results"] = mock_data["results"][:max_results]
        mock_data["total_results"] = len(mock_data["results"])

        # Add cross-terminology mappings if requested
        if request_data.get("include_mappings", True):
            mock_data["cross_mappings"] = {
                "icd_10_to_snomed": {
                    "E11.9": ["44054006"],
                    "E11": ["44054006"]
                },
                "snomed_to_icd_10": {
                    "44054006": ["E11.9", "E11"]
                },
                "mapping_confidence": 0.92
            }

        # Add validation results for specific search types
        if search_type == "term_validation":
            mock_data["validation_results"] = {
                "is_valid_term": True,
                "standardized_form": "Type 2 diabetes mellitus",
                "recommended_codes": ["E11.9", "44054006"],
                "validation_confidence": 0.94,
                "suggestions": [
                    "Consider specifying complications if present",
                    "Use E11.65 if hyperglycemia documented"
                ]
            }

        elif search_type == "code_lookup":
            if mock_data["results"]:
                mock_data["code_details"] = mock_data["results"][0]
                mock_data["code_validity"] = {
                    "is_valid": True,
                    "is_active": True,
                    "effective_date": "2023-10-01",
                    "version": "2024"
                }

        # Add hierarchy information if requested
        if request_data.get("include_hierarchy", True):
            for result in mock_data["results"]:
                if "hierarchy" not in result and result["system"] == "icd_10_cm":
                    result["hierarchy"] = {
                        "level_1": "Chapter",
                        "level_2": "Block",
                        "level_3": "Category",
                        "level_4": "Subcategory"
                    }

        return mock_data

    def process_healthcare_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process medical terminology request with healthcare-specific logic."""
        # Log PHI access for audit trail (terminology data is generally not PHI)
        self._log_phi_access("medical_terminology_access", ["medical_codes", "clinical_terms"])

        # Validate search type
        valid_types = [
            "exact_match", "fuzzy_search", "code_lookup",
            "term_validation", "code_mapping", "hierarchy_search"
        ]

        search_type = request_data.get("search_type")
        if search_type not in valid_types:
            raise ValueError(f"Invalid search type. Must be one of: {valid_types}")

        # Validate terminology system
        valid_systems = [
            "icd_10_cm", "icd_10_pcs", "cpt", "hcpcs",
            "snomed_ct", "loinc", "rxnorm", "ndc", "all_systems"
        ]

        terminology_system = request_data.get("terminology_system")
        if terminology_system not in valid_systems:
            raise ValueError(f"Invalid terminology system. Must be one of: {valid_systems}")

        # Validate that at least one search parameter is provided
        medical_term = request_data.get("medical_term", "")
        medical_code = request_data.get("medical_code", "")

        if not medical_term and not medical_code:
            # Allow empty searches for browsing, but limit results
            pass

        # Validate confidence threshold
        try:
            confidence_threshold = float(request_data.get("confidence_threshold", "0.8"))
            if not 0.0 <= confidence_threshold <= 1.0:
                raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        except ValueError:
            raise ValueError("Invalid confidence threshold format")

        # In production, this would connect to actual medical terminology services
        # For now, return comprehensive mock data
        return self.get_mock_response(request_data)

    def run(
        self,
        medical_term: str = "",
        medical_code: str = "",
        terminology_system: str = "all_systems",
        search_type: str = "fuzzy_search",
        include_synonyms: bool = True,
        include_hierarchy: bool = True,
        include_mappings: bool = True,
        validate_active_only: bool = True,
        confidence_threshold: str = "0.8",
        max_results: str = "10",
        **kwargs
    ) -> Data:
        """
        Execute medical terminology validation and lookup workflow.

        Args:
            medical_term: Medical term or description to validate
            medical_code: Medical code to validate or lookup
            terminology_system: Medical terminology system to use
            search_type: Type of terminology search
            include_synonyms: Include alternative terms
            include_hierarchy: Include hierarchical relationships
            include_mappings: Include cross-terminology mappings
            validate_active_only: Return only active codes
            confidence_threshold: Minimum confidence score
            max_results: Maximum number of results

        Returns:
            Data: Medical terminology response with healthcare metadata
        """
        request_data = {
            "medical_term": medical_term,
            "medical_code": medical_code,
            "terminology_system": terminology_system,
            "search_type": search_type,
            "include_synonyms": include_synonyms,
            "include_hierarchy": include_hierarchy,
            "include_mappings": include_mappings,
            "validate_active_only": validate_active_only,
            "confidence_threshold": confidence_threshold,
            "max_results": max_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self.execute_healthcare_workflow(request_data)