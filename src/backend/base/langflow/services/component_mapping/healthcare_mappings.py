"""Healthcare connector mappings for HIPAA-compliant components."""

from typing import Dict, Any

from langflow.services.database.models.component_mapping.model import ComponentCategoryEnum


HEALTHCARE_CONNECTOR_MAPPINGS = {
    "genesis:ehr_connector": {
        "component": "EHRConnector",
        "config": {
            "ehr_system": "epic",
            "fhir_version": "R4",
            "authentication_type": "oauth2",
            "hipaa_compliance": True,
            "audit_logging": True,
            "encryption_enabled": True,
        },
        "category": ComponentCategoryEnum.HEALTHCARE,
        "healthcare_metadata": {
            "hipaa_compliant": True,
            "phi_handling": True,
            "encryption_required": True,
            "audit_trail": True,
            "medical_standards": ["FHIR R4", "HL7 v2.x"],
            "data_classification": "PHI",
            "compliance_frameworks": ["HIPAA", "HITECH"],
            "security_requirements": {
                "encryption_at_rest": True,
                "encryption_in_transit": True,
                "access_logging": True,
                "role_based_access": True,
                "minimum_permissions": True,
            },
            "interoperability": {
                "fhir_versions": ["R4", "STU3"],
                "hl7_versions": ["2.5", "2.6", "2.7"],
                "supported_resources": [
                    "Patient", "Observation", "Condition",
                    "Medication", "Procedure", "Encounter"
                ],
            },
        },
        "io_mapping": {
            "component": "EHRConnector",
            "dataType": "Data",
            "input_field": "patient_query",
            "output_field": "ehr_data",
            "input_types": ["str", "Message", "Data"],
            "output_types": ["Data"],
        },
        "description": "HIPAA-compliant Electronic Health Record connector supporting FHIR R4 and HL7 standards",
        "version": "1.0.0",
    },

    "genesis:claims_connector": {
        "component": "ClaimsConnector",
        "config": {
            "clearinghouse": "change_healthcare",
            "edi_version": "5010",
            "test_mode": True,
            "hipaa_compliance": True,
            "audit_logging": True,
            "encryption_enabled": True,
        },
        "category": ComponentCategoryEnum.HEALTHCARE,
        "healthcare_metadata": {
            "hipaa_compliant": True,
            "phi_handling": True,
            "encryption_required": True,
            "audit_trail": True,
            "medical_standards": ["X12 EDI 5010", "ANSI ASC X12"],
            "data_classification": "PHI",
            "compliance_frameworks": ["HIPAA", "HITECH"],
            "security_requirements": {
                "encryption_at_rest": True,
                "encryption_in_transit": True,
                "access_logging": True,
                "role_based_access": True,
                "minimum_permissions": True,
            },
            "transaction_types": {
                "837P": "Professional Claims",
                "837I": "Institutional Claims",
                "837D": "Dental Claims",
                "835": "Electronic Remittance Advice",
                "276": "Claims Status Inquiry",
                "277": "Claims Status Response",
            },
        },
        "io_mapping": {
            "component": "ClaimsConnector",
            "dataType": "Data",
            "input_field": "claim_data",
            "output_field": "claim_response",
            "input_types": ["str", "Data"],
            "output_types": ["Data"],
        },
        "description": "HIPAA-compliant claims processing connector supporting X12 EDI transactions",
        "version": "1.0.0",
    },

    "genesis:eligibility_connector": {
        "component": "EligibilityConnector",
        "config": {
            "eligibility_service": "availity",
            "real_time_mode": True,
            "cache_duration_minutes": 15,
            "hipaa_compliance": True,
            "audit_logging": True,
        },
        "category": ComponentCategoryEnum.HEALTHCARE,
        "healthcare_metadata": {
            "hipaa_compliant": True,
            "phi_handling": True,
            "encryption_required": True,
            "audit_trail": True,
            "medical_standards": ["X12 EDI 270/271"],
            "data_classification": "PHI",
            "compliance_frameworks": ["HIPAA", "HITECH"],
            "security_requirements": {
                "encryption_at_rest": True,
                "encryption_in_transit": True,
                "access_logging": True,
                "role_based_access": True,
                "minimum_permissions": True,
            },
            "eligibility_checks": {
                "real_time_verification": True,
                "benefit_details": True,
                "coverage_periods": True,
                "copay_deductible": True,
                "network_status": True,
            },
        },
        "io_mapping": {
            "component": "EligibilityConnector",
            "dataType": "Data",
            "input_field": "eligibility_request",
            "output_field": "eligibility_response",
            "input_types": ["str", "Data"],
            "output_types": ["Data"],
        },
        "description": "HIPAA-compliant insurance eligibility verification connector",
        "version": "1.0.0",
    },

    "genesis:pharmacy_connector": {
        "component": "PharmacyConnector",
        "config": {
            "pharmacy_network": "surescripts",
            "interaction_checking": True,
            "formulary_checking": True,
            "hipaa_compliance": True,
            "audit_logging": True,
        },
        "category": ComponentCategoryEnum.HEALTHCARE,
        "healthcare_metadata": {
            "hipaa_compliant": True,
            "phi_handling": True,
            "encryption_required": True,
            "audit_trail": True,
            "medical_standards": ["NCPDP SCRIPT", "RxNorm", "NDC"],
            "data_classification": "PHI",
            "compliance_frameworks": ["HIPAA", "HITECH", "DEA"],
            "security_requirements": {
                "encryption_at_rest": True,
                "encryption_in_transit": True,
                "access_logging": True,
                "role_based_access": True,
                "minimum_permissions": True,
                "dea_compliance": True,
            },
            "pharmacy_features": {
                "e_prescribing": True,
                "drug_interactions": True,
                "formulary_check": True,
                "prior_authorization": True,
                "medication_therapy_management": True,
            },
        },
        "io_mapping": {
            "component": "PharmacyConnector",
            "dataType": "Data",
            "input_field": "prescription_data",
            "output_field": "pharmacy_response",
            "input_types": ["str", "Data"],
            "output_types": ["Data"],
        },
        "description": "HIPAA-compliant pharmacy and medication management connector",
        "version": "1.0.0",
    },

    "genesis:prior_authorization": {
        "component": "PriorAuthorizationTool",
        "config": {
            "pa_service": "change_healthcare",
            "real_time_mode": True,
            "hipaa_compliance": True,
            "audit_logging": True,
        },
        "category": ComponentCategoryEnum.HEALTHCARE,
        "healthcare_metadata": {
            "hipaa_compliant": True,
            "phi_handling": True,
            "encryption_required": True,
            "audit_trail": True,
            "medical_standards": ["X12 EDI 278", "HL7 FHIR"],
            "data_classification": "PHI",
            "compliance_frameworks": ["HIPAA", "HITECH"],
            "security_requirements": {
                "encryption_at_rest": True,
                "encryption_in_transit": True,
                "access_logging": True,
                "role_based_access": True,
                "minimum_permissions": True,
            },
            "prior_auth_features": {
                "real_time_decisions": True,
                "status_tracking": True,
                "appeals_process": True,
                "documentation_requirements": True,
            },
        },
        "io_mapping": {
            "component": "PriorAuthorizationTool",
            "dataType": "Data",
            "input_field": "pa_request",
            "output_field": "pa_response",
            "input_types": ["str", "Data"],
            "output_types": ["Data"],
        },
        "description": "HIPAA-compliant prior authorization processing tool",
        "version": "1.0.0",
    },

    "genesis:clinical_decision_support": {
        "component": "ClinicalDecisionSupportTool",
        "config": {
            "cds_service": "epic_cds",
            "alert_level": "moderate",
            "hipaa_compliance": True,
            "audit_logging": True,
        },
        "category": ComponentCategoryEnum.HEALTHCARE,
        "healthcare_metadata": {
            "hipaa_compliant": True,
            "phi_handling": True,
            "encryption_required": True,
            "audit_trail": True,
            "medical_standards": ["HL7 CDS Hooks", "FHIR R4"],
            "data_classification": "PHI",
            "compliance_frameworks": ["HIPAA", "HITECH", "FDA"],
            "security_requirements": {
                "encryption_at_rest": True,
                "encryption_in_transit": True,
                "access_logging": True,
                "role_based_access": True,
                "minimum_permissions": True,
                "clinical_validation": True,
            },
            "cds_features": {
                "drug_interactions": True,
                "allergy_alerts": True,
                "dosage_guidance": True,
                "clinical_guidelines": True,
                "evidence_based_recommendations": True,
            },
        },
        "io_mapping": {
            "component": "ClinicalDecisionSupportTool",
            "dataType": "Data",
            "input_field": "clinical_data",
            "output_field": "cds_recommendations",
            "input_types": ["str", "Data"],
            "output_types": ["Data"],
        },
        "description": "HIPAA-compliant clinical decision support tool with evidence-based recommendations",
        "version": "1.0.0",
    },
}


HEALTHCARE_RUNTIME_ADAPTERS = {
    "genesis:ehr_connector": {
        "langflow": {
            "target_component": "EHRConnector",
            "adapter_config": {
                "component_class": "EHRConnector",
                "input_mapping": {
                    "patient_query": "input_value",
                },
                "output_mapping": {
                    "ehr_data": "data",
                },
                "healthcare_specific": {
                    "phi_fields": ["patient_id", "patient_name", "dob", "ssn"],
                    "encryption_fields": ["ssn", "patient_data"],
                    "audit_actions": ["read", "write", "search", "export"],
                },
            },
            "compliance_rules": {
                "minimum_log_level": "INFO",
                "phi_encryption": True,
                "access_control": "RBAC",
                "audit_retention_days": 2555,  # 7 years
                "data_masking": True,
            },
            "version": "1.0.0",
            "priority": 100,
        },
    },

    "genesis:claims_connector": {
        "langflow": {
            "target_component": "ClaimsConnector",
            "adapter_config": {
                "component_class": "ClaimsConnector",
                "input_mapping": {
                    "claim_data": "input_value",
                },
                "output_mapping": {
                    "claim_response": "data",
                },
                "healthcare_specific": {
                    "phi_fields": ["patient_id", "member_id", "provider_npi"],
                    "edi_validation": True,
                    "transaction_logging": True,
                },
            },
            "compliance_rules": {
                "minimum_log_level": "INFO",
                "edi_validation": True,
                "transaction_integrity": True,
                "audit_retention_days": 2555,
                "hipaa_compliance": True,
            },
            "version": "1.0.0",
            "priority": 100,
        },
    },

    "genesis:eligibility_connector": {
        "langflow": {
            "target_component": "EligibilityConnector",
            "adapter_config": {
                "component_class": "EligibilityConnector",
                "input_mapping": {
                    "eligibility_request": "input_value",
                },
                "output_mapping": {
                    "eligibility_response": "data",
                },
                "healthcare_specific": {
                    "phi_fields": ["member_id", "patient_id", "subscriber_id"],
                    "real_time_verification": True,
                    "cache_sensitive_data": False,
                },
            },
            "compliance_rules": {
                "minimum_log_level": "INFO",
                "cache_phi": False,
                "real_time_only": True,
                "audit_retention_days": 2555,
                "hipaa_compliance": True,
            },
            "version": "1.0.0",
            "priority": 100,
        },
    },

    "genesis:pharmacy_connector": {
        "langflow": {
            "target_component": "PharmacyConnector",
            "adapter_config": {
                "component_class": "PharmacyConnector",
                "input_mapping": {
                    "prescription_data": "input_value",
                },
                "output_mapping": {
                    "pharmacy_response": "data",
                },
                "healthcare_specific": {
                    "phi_fields": ["patient_id", "prescriber_npi", "dea_number"],
                    "controlled_substances": True,
                    "drug_interaction_check": True,
                },
            },
            "compliance_rules": {
                "minimum_log_level": "INFO",
                "dea_compliance": True,
                "controlled_substance_logging": True,
                "audit_retention_days": 2555,
                "hipaa_compliance": True,
            },
            "version": "1.0.0",
            "priority": 100,
        },
    },
}


def get_healthcare_component_mappings() -> Dict[str, Any]:
    """Get all healthcare component mappings."""
    return HEALTHCARE_CONNECTOR_MAPPINGS


def get_healthcare_runtime_adapters() -> Dict[str, Any]:
    """Get all healthcare runtime adapters."""
    return HEALTHCARE_RUNTIME_ADAPTERS


def get_healthcare_mapping_by_type(genesis_type: str) -> Dict[str, Any]:
    """Get specific healthcare mapping by genesis type."""
    return HEALTHCARE_CONNECTOR_MAPPINGS.get(genesis_type, {})


def get_healthcare_adapter_by_type(genesis_type: str, runtime_type: str = "langflow") -> Dict[str, Any]:
    """Get specific healthcare runtime adapter."""
    adapters = HEALTHCARE_RUNTIME_ADAPTERS.get(genesis_type, {})
    return adapters.get(runtime_type, {})