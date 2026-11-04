"""Prepare explicit input paths and a credential-free environment for the CLI child."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

if TYPE_CHECKING:
    from collections.abc import Mapping

_RUNTIME_ENVIRONMENT = frozenset(
    {
        "PATH",
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TMPDIR",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
    }
)


def child_environment(config_dir: str, inherited: Mapping[str, str]) -> dict[str, str]:
    """Retain interpreter essentials while dropping provider and application credentials."""
    env = {name: value for name, value in inherited.items() if name.upper() in _RUNTIME_ENVIRONMENT}
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = os.pathsep.join(
            str(Path(path or ".").expanduser().resolve()) for path in env["PYTHONPATH"].split(os.pathsep)
        )
    env.update(
        HOME=config_dir,
        USERPROFILE=config_dir,
        APPDATA=config_dir,
        LOCALAPPDATA=config_dir,
        XDG_CONFIG_HOME=config_dir,
        XDG_CACHE_HOME=config_dir,
        XDG_DATA_HOME=config_dir,
        LANGFLOW_CONFIG_DIR=config_dir,
        DO_NOT_TRACK="true",
        LITELLM_LOCAL_MODEL_COST_MAP="True",
        HF_HUB_OFFLINE="1",
        HF_DATASETS_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
    )
    return env


def resolve_input_paths(options: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve selected local paths before the child leaves the caller's home and directory."""
    selected = {**options, "settings": dict(options["settings"])}
    selected["settings"]["components_path"] = [
        str(Path(path).expanduser().resolve()) for path in options["settings"]["components_path"]
    ]
    if options.get("output"):
        selected["output"] = str(Path(options["output"]).expanduser().resolve())
    for name in ("database_url", "serving_database_url"):
        if not options.get(name):
            continue
        try:
            url = sa.make_url(options[name])
        except (sa.exc.ArgumentError, ValueError):
            # The child reports invalid source URLs through its structured error channel.
            continue
        if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
            url = url.set(database=str(Path(url.database).expanduser().resolve()))
        elif url.get_backend_name() in {"postgres", "postgresql"}:
            paths = {
                key: str(Path(value).expanduser().resolve())
                for key, value in url.query.items()
                if key in {"sslcert", "sslkey", "sslrootcert", "sslcrl", "sslcrldir", "passfile"}
                and isinstance(value, str)
                and value
                and value != "system"
            }
            url = url.update_query_dict(paths)
        selected[name] = url.render_as_string(hide_password=False)
    return selected
