"""Pure MCP config-secret helpers shared by the API layer and the export scrubber.

Deliberately dependency-free, like ``langflow.utils.flow_secrets``: it must be
importable without pulling in FastAPI or the service layer. ``langflow.utils.flow_secrets``
imports this module at load time to clean an MCP server's ``config`` for a strict
deployment snapshot; if these helpers lived in ``langflow.api.utils.mcp.flow_secrets``
(which pulls in the whole API router tree) that import would be circular whenever
something imports the scrubber before ``langflow.api.v1``.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

SECRET_CONFIG_FIELDS = ("api_key", "apiKey", "authorization", "Authorization")

# Headers that are part of the HTTP conversation, never a credential. An allowlist of
# known non-secrets, deliberately not a heuristic for "looks secret": guessing which
# values are sensitive fails open into a leak, while these specific names cannot be one.
NON_SECRET_HEADERS = frozenset(
    {
        "accept",
        "accept-charset",
        "accept-encoding",
        "accept-language",
        "cache-control",
        "content-type",
        "user-agent",
    }
)

HEADER_ARG_FLAG = "--headers"

VARIABLE_PREFIX = "MCP_"

PLACEHOLDER_PATTERN = re.compile(r"^\{\{\s*[A-Za-z_][A-Za-z0-9_\-]*\s*\}\}$")

# Sub-maps of an ``mcpServers`` entry whose *values* carry secrets (API keys,
# bearer tokens) and must be encrypted at rest in the mcp_server table.
MCP_SECRET_CONFIG_MAPS = ("env", "headers")


def _is_variable_reference(value: str) -> bool:
    """Whether a value is already a reference, so a re-save does not wrap it twice.

    Recognising any capitalised token failed open on the alphabet of the secret: an AWS
    access key id, or any uppercase hex token, reads as a reference and was copied into
    the flow verbatim. Only the two shapes this system can actually resolve count — the
    names generated below, and the explicit ``{{NAME}}`` placeholder.
    """
    return bool(PLACEHOLDER_PATTERN.match(value)) or value.startswith(VARIABLE_PREFIX)


def _strip_header_args(args: list[Any]) -> tuple[list[Any], bool]:
    """Drop ``--headers <name> <value>`` triples, which is where auto-install bakes the key."""
    cleaned: list[Any] = []
    found = False
    index = 0
    while index < len(args):
        if args[index] == HEADER_ARG_FLAG and index + 2 < len(args):
            found = True
            index += 3
            continue
        cleaned.append(args[index])
        index += 1
    return cleaned, found


def variable_name_for(server_name: str, key: str) -> str:
    """Build the global-variable name that replaces a literal secret.

    Deterministic so a re-save of the same server lands on the same variable instead of
    minting a new one on every write.

    The digest is what makes the name injective. Slugifying alone collapsed
    ``billing-mcp``, ``billing_mcp`` and ``billing.mcp`` onto one name, and because an
    existing variable is never overwritten the second server would silently authenticate
    to its own target using the first server's credential.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{server_name}_{key}").strip("_").upper()
    digest = hashlib.sha256(f"{server_name}\0{key}".encode()).hexdigest()[:8].upper()
    return f"{VARIABLE_PREFIX}{slug}_{digest}"


def strip_config_secrets(config: dict[str, Any], server_name: str) -> tuple[dict[str, Any], dict[str, str], bool]:
    """Swap literal secrets for global-variable names.

    A reference rather than a blank: a config with an empty ``headers`` names nothing, so
    a stateless runtime (``lfx serve``, which has no ``mcp_server`` table) has no way to
    restore the credential. The name keeps the flow self-describing and portable.

    Returns the rewritten config, the variable name to value map that has to exist for it
    to resolve, and whether anything was rewritten.
    """
    stripped = dict(config)
    variables: dict[str, str] = {}
    found = False

    for key in MCP_SECRET_CONFIG_MAPS:
        value = stripped.get(key)
        if isinstance(value, dict) and value:
            referenced = {}
            for entry_key, entry_value in value.items():
                skip = key == "headers" and str(entry_key).lower() in NON_SECRET_HEADERS
                if (
                    not skip
                    and isinstance(entry_value, str)
                    and entry_value
                    and not _is_variable_reference(entry_value)
                ):
                    name = variable_name_for(server_name, entry_key)
                    variables[name] = entry_value
                    referenced[entry_key] = name
                    found = True
                else:
                    referenced[entry_key] = entry_value
            stripped[key] = referenced

    for field in SECRET_CONFIG_FIELDS:
        if stripped.get(field):
            del stripped[field]
            found = True

    args = stripped.get("args")
    if isinstance(args, list):
        cleaned_args, had_header_args = _strip_header_args(args)
        if had_header_args:
            stripped["args"] = cleaned_args
            found = True

    return stripped, variables, found


__all__ = [
    "HEADER_ARG_FLAG",
    "MCP_SECRET_CONFIG_MAPS",
    "NON_SECRET_HEADERS",
    "PLACEHOLDER_PATTERN",
    "SECRET_CONFIG_FIELDS",
    "VARIABLE_PREFIX",
    "strip_config_secrets",
    "variable_name_for",
]
