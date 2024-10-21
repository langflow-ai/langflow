import os.path

# we need to import tmpdir


def get_required_env_var(var: str) -> str:
    """Get the value of the specified environment variable.

    Args:
    var (str): The environment variable to get.

    Returns:
    str: The value of the environment variable.

    Raises:
    ValueError: If the environment variable is not set.
    """
    value = os.getenv(var)
    if not value:
        msg = f"Environment variable {var} is not set"
        raise ValueError(msg)
    return value


def get_openai_api_key() -> str:
    return get_required_env_var("OPENAI_API_KEY")


def get_astradb_application_token() -> str:
    return get_required_env_var("ASTRA_DB_APPLICATION_TOKEN")


def get_astradb_api_endpoint() -> str:
    return get_required_env_var("ASTRA_DB_API_ENDPOINT")
