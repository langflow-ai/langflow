"""Prepare explicit input paths and a credential-free environment for the CLI child."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import sqlalchemy as sa

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
_CHILD_ENVIRONMENT = frozenset(
    {
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "LANGFLOW_CONFIG_DIR",
        "DO_NOT_TRACK",
        "LITELLM_LOCAL_MODEL_COST_MAP",
        "OTEL_SEMCONV_STABILITY_OPT_IN",
        "HF_HUB_OFFLINE",
        "HF_DATASETS_OFFLINE",
        "TRANSFORMERS_OFFLINE",
    }
)


def is_local_metadata_probe(arguments: tuple[Any, ...]) -> bool:
    """Allow only proven system metadata probes with an unmodified sanitized environment."""
    try:
        executable, argv, _cwd, supplied_environment = arguments
    except (TypeError, ValueError):
        return False
    if not isinstance(executable, str) or not isinstance(argv, (list, tuple)) or not argv:
        return False
    if not all(isinstance(argument, str) for argument in argv):
        return False
    if tuple(argv[1:]) == ("version",):
        program = "git"
    else:
        try:
            option, target = argv[1:]
        except ValueError:
            return False
        if (
            option != "-b"
            or not Path(target).is_absolute()
            or (os.path.realpath(target) != os.path.realpath(sys.executable))
        ):
            return False
        program = "file"
    trusted = Path(f"/usr/bin/{program}").resolve()
    allowed = {program, str(trusted)}
    if not trusted.is_file() or executable not in allowed or argv[0] not in allowed:
        return False
    environment = os.environ if supplied_environment is None else supplied_environment
    if not isinstance(environment, Mapping) or environment.get("PATH") != os.defpath:
        return False
    for name, value in environment.items():
        if not isinstance(name, str) or not isinstance(value, str):
            return False
        # GitPython and platform._syscmd_file force C locale for their version/architecture parsers.
        if name in {"LANGUAGE", "LC_ALL"} and value == "C":
            continue
        if name == "PATH":
            continue
        if name.upper() not in _RUNTIME_ENVIRONMENT | _CHILD_ENVIRONMENT or value != os.environ.get(name):
            return False
    resolved = shutil.which(executable, path=os.defpath)
    return resolved is not None and Path(resolved).resolve() == trusted


def child_environment(config_dir: str, inherited: Mapping[str, str]) -> dict[str, str]:
    """Retain interpreter essentials while dropping provider and application credentials."""
    env = {name: value for name, value in inherited.items() if name.upper() in _RUNTIME_ENVIRONMENT}
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = os.pathsep.join(
            str(Path(path or ".").expanduser().resolve()) for path in env["PYTHONPATH"].split(os.pathsep)
        )
    env.update(
        PATH=os.defpath,
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
