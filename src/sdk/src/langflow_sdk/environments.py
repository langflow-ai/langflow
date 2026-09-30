"""Environment configuration for langflow-sdk.

Loads named environment definitions from a TOML file so teams can switch
between Langflow instances (dev / staging / production) without code changes.

Config file lookup order
------------------------
1. Path given explicitly to ``load_environments()`` or ``get_client()``.
2. The ``LANGFLOW_ENVIRONMENTS_FILE`` environment variable.
3. ``langflow-environments.toml`` in the current working directory.
4. ``~/.config/langflow/environments.toml``

File format
-----------
.. code-block:: toml

    [environments.staging]
    url = "https://staging.langflow.example.com"
    api_key_env = "LANGFLOW_STAGING_API_KEY"   # env-var that holds the key  # pragma: allowlist secret

    [environments.production]
    url = "https://langflow.example.com"
    api_key_env = "LANGFLOW_PROD_API_KEY"  # pragma: allowlist secret

    # Optional: set a default so callers don't have to name an environment
    [defaults]
    environment = "staging"
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from langflow_sdk.exceptions import EnvironmentConfigError, EnvironmentNotFoundError

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-reattr,assignment]

_ENV_VAR = "LANGFLOW_ENVIRONMENTS_FILE"
_LOCAL_NAME = "langflow-environments.toml"
_USER_PATH = Path.home() / ".config" / "langflow" / "environments.toml"

_EXAMPLE_CONFIG = """\
# langflow-environments.toml
#
# Define named Langflow environments.  The api_key_env field is the *name*
# of an environment variable that holds the API key for that instance.
#
# [environments.staging]
# url = "https://staging.langflow.example.com"
# api_key_env = "LANGFLOW_STAGING_API_KEY"  # pragma: allowlist secret
#
# [environments.production]
# url = "https://langflow.example.com"
# api_key_env = "LANGFLOW_PROD_API_KEY"  # pragma: allowlist secret
#
# [defaults]
# environment = "staging"
"""


class EnvironmentConfig:
    """A single named environment definition."""

    def __init__(self, name: str, url: str, api_key: str | None) -> None:
        self.name = name
        self.url = url
        self.api_key = api_key

    def __repr__(self) -> str:
        masked = f"{self.api_key[:4]}..." if self.api_key else None
        return f"EnvironmentConfig(name={self.name!r}, url={self.url!r}, api_key={masked!r})"


def _candidate_paths(explicit: Path | str | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env_path = os.environ.get(_ENV_VAR)
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path.cwd() / _LOCAL_NAME)
    candidates.append(_USER_PATH)
    return candidates


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except OSError as exc:
        raise EnvironmentConfigError(f"Cannot read environments file {path}: {exc}") from exc
    except Exception as exc:
        raise EnvironmentConfigError(f"Invalid TOML in {path}: {exc}") from exc


def _parse_env(raw: dict[str, Any], file_path: Path, name: str) -> EnvironmentConfig:
    if "url" not in raw:
        raise EnvironmentConfigError(f"Environment {name!r} in {file_path} is missing the required 'url' field.")
    url: str = raw["url"]
    api_key: str | None = None
    if "api_key_env" in raw:
        api_key_env_name: str = raw["api_key_env"]
        api_key = os.environ.get(api_key_env_name)
    elif "api_key" in raw:
        import warnings

        warnings.warn(
            f"Environment {name!r}: literal api_key in config file is not recommended. "
            "Use api_key_env to reference an environment variable instead.",
            UserWarning,
            stacklevel=2,
        )
        api_key = raw["api_key"]
    return EnvironmentConfig(name=name, url=url, api_key=api_key)


def load_environments(
    config_file: Path | str | None = None,
) -> dict[str, EnvironmentConfig]:
    """Load all environments from the config file.

    Parameters
    ----------
    config_file:
        Explicit path to a ``langflow-environments.toml`` file. If omitted,
        the lookup order described in the module docstring is used.

    Returns:
    -------
    dict[str, EnvironmentConfig]
        Mapping of environment name → ``EnvironmentConfig``.

    Raises:
    ------
    EnvironmentConfigError
        If no config file is found or the file is malformed.
    """
    file_path: Path | None = None
    for candidate in _candidate_paths(config_file):
        if candidate.exists():
            file_path = candidate
            break

    if file_path is None:
        raise EnvironmentConfigError(
            "No langflow-environments.toml found. "
            f"Set {_ENV_VAR} or create one in the current directory.\n\n" + _EXAMPLE_CONFIG
        )

    raw = _load_toml(file_path)
    raw_envs = raw.get("environments", {})
    if not isinstance(raw_envs, dict):
        raise EnvironmentConfigError(f"Expected [environments] to be a TOML table in {file_path}")

    result: dict[str, EnvironmentConfig] = {}
    for name, env_data in raw_envs.items():
        if not isinstance(env_data, dict):
            raise EnvironmentConfigError(f"Environment {name!r} in {file_path} must be a TOML table.")
        result[name] = _parse_env(env_data, file_path, name)
    return result


def get_environment(
    name: str | None = None,
    *,
    config_file: Path | str | None = None,
) -> EnvironmentConfig:
    """Look up a named environment from the config file.

    If *name* is ``None``, the ``[defaults] environment`` key is used.

    Raises:
    ------
    EnvironmentNotFoundError
        If *name* is not defined in the config.
    EnvironmentConfigError
        If no default is set and *name* is ``None``.
    """
    # Find the config file once and reuse for both default lookup and environment loading.
    file_path: Path | None = None
    for candidate in _candidate_paths(config_file):
        if candidate.exists():
            file_path = candidate
            break

    if name is None:
        if file_path:
            raw = _load_toml(file_path)
            name = raw.get("defaults", {}).get("environment")
        if name is None:
            msg = "No environment name given and no [defaults] environment set in the config file."
            raise EnvironmentConfigError(msg)

    environments = load_environments(file_path or config_file)

    if name not in environments:
        raise EnvironmentNotFoundError(name)
    return environments[name]


def get_client(
    environment: str | None = None,
    *,
    config_file: Path | str | None = None,
    timeout: float = 60.0,
) -> Client:  # noqa: F821  (resolved at runtime)
    """Convenience factory: load config and return a ready :class:`Client`.

    Parameters
    ----------
    environment:
        Name of the environment to use (e.g. ``"staging"``). If ``None``,
        the ``[defaults] environment`` key in the config file is used.
    config_file:
        Optional explicit path to the environments TOML file.
    timeout:
        HTTP request timeout in seconds.

    Example::

        from langflow_sdk import get_client

        client = get_client("staging")
        flows  = client.list_flows()
    """
    from langflow_sdk.client import Client

    env = get_environment(environment, config_file=config_file)
    return Client(base_url=env.url, api_key=env.api_key, timeout=timeout)


def get_async_client(
    environment: str | None = None,
    *,
    config_file: Path | str | None = None,
    timeout: float = 60.0,
) -> AsyncClient:  # noqa: F821  (resolved at runtime)
    """Convenience factory: return a ready :class:`AsyncClient`.

    Example::

        from langflow_sdk import get_async_client

        async with get_async_client("staging") as client:
            flows = await client.list_flows()
    """
    from langflow_sdk.client import AsyncClient

    env = get_environment(environment, config_file=config_file)
    return AsyncClient(base_url=env.url, api_key=env.api_key, timeout=timeout)
