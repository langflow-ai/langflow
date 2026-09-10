"""Shared public-contract invocation for Langflow components."""

from typing import Any

from fxmacrodata_public import FXMacroDataClient, FXMacroDataError

SITE_URL = (
    "https://fxmacrodata.com/?utm_source=langflow&utm_medium=integration"
    "&utm_campaign=open_source_integrations&utm_content=app"
)
DOCUMENTATION = (
    "https://fxmacrodata.com/documentation/reference?utm_source=github&utm_medium=referral"
    "&utm_campaign=open_source_integrations&utm_content=langflow_docs"
)


def query(operation: str, arguments: dict[str, Any], api_key: Any = None, timeout: float = 30) -> dict[str, Any]:
    try:
        key = api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else api_key
        with FXMacroDataClient(api_key=key, timeout=timeout) as client:
            result = client.execute(operation, arguments)
        return {**result.as_dict(), "provider_url": SITE_URL, "error": ""}
    except Exception as error:  # noqa: BLE001 - sanitize the external SDK boundary
        return {
            "operation": operation,
            "data": None,
            "records": [],
            "source_url": "https://fxmacrodata.com/documentation/reference",
            "provider_url": SITE_URL,
            "error": str(error)
            if isinstance(error, FXMacroDataError)
            else "FXMacroData request failed. Check parameters and access.",
        }
