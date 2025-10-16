"""Healthcare connectors for HIPAA-compliant medical data integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from langflow.base.healthcare_connector_base import HealthcareConnectorBase
    from langflow.components.healthcare.appeals_data_connector import AppealsDataConnector
    from langflow.components.healthcare.claims_connector import ClaimsConnector
    from langflow.components.healthcare.ehr_connector import EHRConnector
    from langflow.components.healthcare.eligibility_connector import EligibilityConnector
    from langflow.components.healthcare.pharmacy_connector import PharmacyConnector

_dynamic_imports = {
    "HealthcareConnectorBase": "langflow.base.healthcare_connector_base",
    "AppealsDataConnector": "appeals_data_connector",
    "ClaimsConnector": "claims_connector",
    "EHRConnector": "ehr_connector",
    "EligibilityConnector": "eligibility_connector",
    "PharmacyConnector": "pharmacy_connector",
}

__all__ = ["HealthcareConnectorBase", "AppealsDataConnector", "ClaimsConnector", "EHRConnector", "EligibilityConnector", "PharmacyConnector"]


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