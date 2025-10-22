"""Healthcare connectors for HIPAA-compliant medical data integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from langflow.base.healthcare_connector_base import HealthcareConnectorBase
    from langflow.components.healthcare.accumulator_benefits_connector import AccumulatorBenefitsConnector
    from langflow.components.healthcare.appeals_data_connector import AppealsDataConnector
    from langflow.components.healthcare.claims_connector import ClaimsConnector
    from langflow.components.healthcare.clinical_nlp_connector import ClinicalNLPConnector
    from langflow.components.healthcare.clinical_nlp_analyzer_connector import ClinicalNLPAnalyzerConnector
    from langflow.components.healthcare.compliance_data_connector import ComplianceDataConnector
    from langflow.components.healthcare.ehr_connector import EHRConnector
    from langflow.components.healthcare.eligibility_connector import EligibilityConnector
    from langflow.components.healthcare.medical_terminology_connector import MedicalTerminologyConnector
    from langflow.components.healthcare.pharmacy_benefits_connector import PharmacyBenefitsConnector
    from langflow.components.healthcare.pharmacy_connector import PharmacyConnector
    from langflow.components.healthcare.provider_network_connector import ProviderNetworkConnector
    from langflow.components.healthcare.quality_metrics_connector import QualityMetricsConnector
    from langflow.components.healthcare.speech_transcription_connector import SpeechTranscriptionConnector
    from langflow.components.healthcare.document_extraction_connector import DocumentExtractionConnector
    from langflow.components.healthcare.document_management_connector import DocumentManagementConnector
    from langflow.components.healthcare.medical_data_standardizer_connector import MedicalDataStandardizerConnector

_dynamic_imports = {
    "HealthcareConnectorBase": "langflow.base.healthcare_connector_base",
    "AccumulatorBenefitsConnector": "accumulator_benefits_connector",
    "AppealsDataConnector": "appeals_data_connector",
    "ClaimsConnector": "claims_connector",
    "ClinicalNLPConnector": "clinical_nlp_connector",
    "ClinicalNLPAnalyzerConnector": "clinical_nlp_analyzer_connector",
    "ComplianceDataConnector": "compliance_data_connector",
    "EHRConnector": "ehr_connector",
    "EligibilityConnector": "eligibility_connector",
    "MedicalTerminologyConnector": "medical_terminology_connector",
    "PharmacyBenefitsConnector": "pharmacy_benefits_connector",
    "PharmacyConnector": "pharmacy_connector",
    "ProviderNetworkConnector": "provider_network_connector",
    "QualityMetricsConnector": "quality_metrics_connector",
    "SpeechTranscriptionConnector": "speech_transcription_connector",
    "DocumentExtractionConnector": "document_extraction_connector",
    "DocumentManagementConnector": "document_management_connector",
    "MedicalDataStandardizerConnector": "medical_data_standardizer_connector",
}

__all__ = [
    "HealthcareConnectorBase",
    "AccumulatorBenefitsConnector",
    "AppealsDataConnector",
    "ClaimsConnector",
    "ClinicalNLPConnector",
    "ClinicalNLPAnalyzerConnector",
    "ComplianceDataConnector",
    "EHRConnector",
    "EligibilityConnector",
    "MedicalTerminologyConnector",
    "PharmacyBenefitsConnector",
    "PharmacyConnector",
    "ProviderNetworkConnector",
    "QualityMetricsConnector",
    "SpeechTranscriptionConnector",
    "DocumentExtractionConnector",
    "DocumentManagementConnector",
    "MedicalDataStandardizerConnector"
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import healthcare components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        import_path = _dynamic_imports[attr_name]
        if attr_name == "HealthcareConnectorBase":
            # Special handling for base class in different package
            from langflow.base.healthcare_connector_base import HealthcareConnectorBase
            result = HealthcareConnectorBase
        else:
            result = import_mod(attr_name, import_path, __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)