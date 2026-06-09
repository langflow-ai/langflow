"""lfx environment configuration — resolve Langflow instance URL and API key.

Config file lookup order
------------------------
1.  Explicit path given via ``--environments-file`` / ``environments_file`` parameter.
2.  ``.lfx/environments.yaml`` in the current working directory, then each
    parent directory up to the first ``.git`` boundary (project root discovery).
3.  ``~/.lfx/environments.yaml`` (user-level config).
4.  ``langflow-environments.toml`` in the current working directory
    (backward-compatible with the langflow-sdk TOML format).

YAML file format
----------------
.. code-block:: yaml

    environments:
      local:
        url: http://localhost:7860
        api_key_env: LANGFLOW_LOCAL_API_KEY

      staging:
        url: https://staging.langflow.example.com
        api_key_env: LANGFLOW_STAGING_API_KEY

      production:
        url: https://langflow.example.com
        api_key_env: LANGFLOW_PROD_API_KEY

    defaults:
      environment: local

TOML format is also accepted (``langflow-environments.toml`` or any ``.toml``
file passed via ``--environments-file``).

The ``api_key_env`` field names an *environment variable* that holds the API
key.  The actual key is never stored in the file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when the config file is missing, malformed, or an environment name cannot be resolved.

    Note: a missing API key env var is *not* a ``ConfigError`` — ``api_key``
    will simply be ``None`` on the returned :class:`LangflowEnvironment`.
    Commands that require a key validate it themselves and raise an appropriate
    error with actionable guidance.
    """


@dataclass
class LangflowEnvironment:
    """A fully-resolved Langflow target instance.

    Attributes:
        name:    Human-readable label (environment name or ``"__inline__"``).
        url:     Base URL of the Langflow instance.
        api_key: Resolved API key value, or ``None`` if not configured.
    """

    name: str
    url: str
    api_key: str | None


# ---------------------------------------------------------------------------
# Config file discovery
# ---------------------------------------------------------------------------

_YAML_NAMES: tuple[str, ...] = ("environments.yaml", "environments.yml")
_TOML_FALLBACK = "langflow-environments.toml"
_LFX_DIR = ".lfx"


def _find_config_file(override: Path | None) -> Path | None:
    """Return the first existing config file following the lookup order.

    Parameters
    ----------
    override:
        Explicit path supplied by the caller (``--environments-file``).
        If given, only this path is checked.

    Raises:
    ------
    ConfigError:
        If *override* is given but the file does not exist.
    """
    if override is not None:
        if not override.is_file():
            msg = f"Config file not found: {override}"
            raise ConfigError(msg)
        return override

    # Walk up from cwd looking for .lfx/environments.yaml
    cwd = Path.cwd()
    for directory in (cwd, *cwd.parents):
        for name in _YAML_NAMES:
            candidate = directory / _LFX_DIR / name
            if candidate.is_file():
                return candidate
        # Stop walking at a git root or the filesystem root
        if (directory / ".git").is_dir() or directory.parent == directory:
            break

    # User-level YAML
    for name in _YAML_NAMES:
        user_yaml = Path.home() / _LFX_DIR / name
        if user_yaml.is_file():
            return user_yaml

    # Backward-compat: langflow-environments.toml in cwd
    toml_fallback = cwd / _TOML_FALLBACK
    if toml_fallback.is_file():
        return toml_fallback

    return None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_yaml(text: str, path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        msg = "PyYAML is required to read .yaml config files. Install it with: pip install pyyaml"
        raise ConfigError(msg) from exc
    try:
        result = yaml.safe_load(text)
    except Exception as exc:
        msg = f"Invalid YAML in {path}: {exc}"
        raise ConfigError(msg) from exc
    if not isinstance(result, dict):
        msg = f"Expected a YAML mapping at the top level of {path}, got {type(result).__name__}"
        raise ConfigError(msg)
    return result


def _parse_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-reattr,assignment]
        except ImportError as exc:
            msg = "tomllib (Python ≥3.11) or tomli is required for .toml config files. Install with: pip install tomli"
            raise ConfigError(msg) from exc
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except OSError as exc:
        msg = f"Cannot read {path}: {exc}"
        raise ConfigError(msg) from exc
    except Exception as exc:
        msg = f"Invalid TOML in {path}: {exc}"
        raise ConfigError(msg) from exc


def _load_raw(path: Path) -> dict[str, Any]:
    """Return the raw parsed config dict from *path* (YAML or TOML)."""
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return _parse_yaml(path.read_text(encoding="utf-8"), path)
    if suffix == ".toml":
        return _parse_toml(path)
    # Unknown extension — try YAML first, then TOML
    try:
        return _parse_yaml(path.read_text(encoding="utf-8"), path)
    except ConfigError:
        return _parse_toml(path)


def _parse_env_block(name: str, block: Any, config_path: Path) -> LangflowEnvironment:
    if not isinstance(block, dict):
        msg = f"Environment {name!r} in {config_path} must be a mapping, got {type(block).__name__}"
        raise ConfigError(msg)
    if "url" not in block:
        msg = f"Environment {name!r} in {config_path} is missing the required 'url' field."
        raise ConfigError(msg)
    url: str = str(block["url"])
    api_key: str | None = None

    if "api_key_env" in block:
        var_name: str = str(block["api_key_env"])
        api_key = os.environ.get(var_name)
        # api_key may be None here; callers that require a key raise their own error.
    elif "api_key" in block:
        import warnings

        warnings.warn(
            f"Environment {name!r}: literal api_key in config file is not recommended. "
            "Use api_key_env to reference an environment variable instead.",
            UserWarning,
            stacklevel=2,
        )
        api_key = str(block["api_key"])

    return LangflowEnvironment(name=name, url=url, api_key=api_key)


def _load_config(path: Path) -> tuple[dict[str, LangflowEnvironment], str | None]:
    """Return ``(environments_dict, default_env_name)`` from the config at *path*."""
    raw = _load_raw(path)

    raw_envs: Any = raw.get("environments") or {}
    if not isinstance(raw_envs, dict):
        msg = f"'environments' in {path} must be a mapping, got {type(raw_envs).__name__}"
        raise ConfigError(msg)

    envs: dict[str, LangflowEnvironment] = {}
    for env_name, block in raw_envs.items():
        envs[str(env_name)] = _parse_env_block(str(env_name), block, path)

    defaults: Any = raw.get("defaults") or {}
    default_name: str | None = defaults.get("environment") if isinstance(defaults, dict) else None

    return envs, default_name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_environment(
    env: str | None,
    *,
    target: str | None = None,
    api_key: str | None = None,
    environments_file: str | None = None,
) -> LangflowEnvironment:
    """Resolve an environment name (or inline flags) to a :class:`LangflowEnvironment`.

    Precedence
    ----------
    1. **Inline mode** — if *target* is given, return immediately without
       reading any config file.  *api_key* is used as-is (its value, not a
       variable name).
    2. **Named env** — look up *env* (or the configured default) in the config
       file discovered by the lookup order described in this module's docstring.
    3. **Env-var fallback** — if no config file exists and no *env* was
       requested, fall back to ``LANGFLOW_URL`` / ``LANGFLOW_API_KEY`` (or
       ``LFX_URL`` / ``LFX_API_KEY``) env vars before raising.

    Parameters
    ----------
    env:
        Environment name from the config file (e.g. ``"staging"``).
    target:
        Inline URL override — bypasses config file lookup entirely.
    api_key:
        Inline API key value.  When used with *target*, taken as-is.
        When used alongside an *env* from the config, overrides the resolved key.
    environments_file:
        Explicit path to a config file (YAML or TOML).  Overrides the
        automatic discovery order.

    Returns:
    -------
    LangflowEnvironment:
        Fully-resolved environment with ``url`` and ``api_key``.

    Raises:
    ------
    ConfigError:
        When resolution fails: file not found, unknown environment name,
        malformed config, etc.
    """
    # -----------------------------------------------------------------------
    # Mode 1: inline (--target provided)
    # -----------------------------------------------------------------------
    if target is not None:
        name = env or "__inline__"
        return LangflowEnvironment(name=name, url=target, api_key=api_key)

    # -----------------------------------------------------------------------
    # Mode 2: config file
    # -----------------------------------------------------------------------
    override = Path(environments_file) if environments_file else None
    config_path = _find_config_file(override)

    if config_path is None:
        # No config file found — try env-var fallback before giving up
        lf_url = os.environ.get("LANGFLOW_URL") or os.environ.get("LFX_URL")
        if lf_url and env is None:
            lf_key = api_key or os.environ.get("LANGFLOW_API_KEY") or os.environ.get("LFX_API_KEY")
            return LangflowEnvironment(name="__env__", url=lf_url, api_key=lf_key)

        if env is not None:
            msg = (
                f"Environment {env!r} requested but no config file was found.\n"
                f"  • Create .lfx/environments.yaml in your project root, or\n"
                f"  • Pass --target <url> [--api-key <key>] for inline configuration.\n"
                f"  • Run 'lfx init' to scaffold a project with a config template."
            )
            raise ConfigError(msg)

        msg = (
            "No --env, --target URL, or config file found.\n"
            "Options:\n"
            "  • lfx <cmd> --env <name>              (requires .lfx/environments.yaml)\n"
            "  • lfx <cmd> --target <url>             (inline, no config file needed)\n"
            "  • export LANGFLOW_URL=<url>            (env-var fallback)\n"
            "  • lfx init                             (scaffold a project with a template)"
        )
        raise ConfigError(msg)

    all_envs, default_name = _load_config(config_path)

    resolved_name = env or default_name
    if resolved_name is None:
        available = ", ".join(sorted(all_envs)) or "(none defined)"
        msg = (
            f"No --env given and no 'defaults.environment' set in {config_path}.\n"
            f"Available environments: {available}\n"
            f"Pass --env <name> or add a 'defaults.environment' key to the config."
        )
        raise ConfigError(msg)

    if resolved_name not in all_envs:
        available = ", ".join(sorted(all_envs)) or "(none defined)"
        msg = f"Environment {resolved_name!r} not found in {config_path}.\nAvailable environments: {available}"
        raise ConfigError(msg)

    resolved = all_envs[resolved_name]

    # --api-key overrides the key resolved from the config file
    if api_key is not None:
        resolved = LangflowEnvironment(name=resolved.name, url=resolved.url, api_key=api_key)

    return resolved
