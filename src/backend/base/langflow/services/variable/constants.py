CREDENTIAL_TYPE = "Credential"
GENERIC_TYPE = "Generic"
OAUTH_REGISTRATION_VARIABLE_PREFIX = "LANGFLOW_OAUTH_REGISTRATION__"


def is_oauth_registration_variable(name: str | None) -> bool:
    """Identify instance OAuth settings reserved for the provider management API."""
    return bool(name and name.startswith(OAUTH_REGISTRATION_VARIABLE_PREFIX))
