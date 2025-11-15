import os

import pytest

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
    if not value.strip():
        msg = f"Environment variable {var} is empty"
        raise ValueError(msg)
    if value == "dummy":
        msg = f"Environment variable {var} is set to dummy"
        raise ValueError(msg)
    return value


def get_openai_api_key() -> str:
    try:
        return get_required_env_var("OPENAI_API_KEY")
    except ValueError:
        pytest.skip("OPENAI_API_KEY is not set")


def get_astradb_application_token() -> str:
    return get_required_env_var("ASTRA_DB_APPLICATION_TOKEN")


def get_astradb_api_endpoint() -> str:
    return get_required_env_var("ASTRA_DB_API_ENDPOINT")


def has_api_key(env_var: str) -> bool:
    """Return True if the given env var exists and is non-empty after stripping."""
    try:
        bool(get_required_env_var(env_var))
    except ValueError:
        return False
    return True


# Cassandra/ScyllaDB credentials
def get_cassandra_host() -> str:
    """Get Cassandra host from environment, default to localhost."""
    return os.getenv("CASSANDRA_HOST", "localhost")


def get_cassandra_port() -> int:
    """Get Cassandra port from environment, default to 9043."""
    return int(os.getenv("CASSANDRA_PORT", "9043"))


def get_cassandra_keyspace() -> str:
    """Get Cassandra keyspace from environment, default to langflow_test."""
    return os.getenv("CASSANDRA_KEYSPACE", "langflow_test")


def get_scylladb_host() -> str:
    """Get ScyllaDB host from environment, default to localhost."""
    return os.getenv("SCYLLADB_HOST", "localhost")


def get_scylladb_port() -> int:
    """Get ScyllaDB port from environment, default to 9042."""
    return int(os.getenv("SCYLLADB_PORT", "9042"))


def get_scylladb_keyspace() -> str:
    """Get ScyllaDB keyspace from environment, default to langflow_test."""
    return os.getenv("SCYLLADB_KEYSPACE", "langflow_test")
