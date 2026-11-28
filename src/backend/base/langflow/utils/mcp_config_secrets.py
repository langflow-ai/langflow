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
from urllib.parse import urlparse

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

# A Langflow project's own MCP endpoint, as ``_build_project_url`` composes it in
# ``langflow.api.utils.mcp.config_utils``. Match only the parsed path, at the root or
# after the configured public MCP base path, so a query string cannot supply the route.
_PROJECT_MCP_PATH = re.compile(
    r"^/api/v1/mcp/project/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:/|$)"
)


def variable_reference_name(value: object) -> str | None:
    """The global variable a config value defers to, or None when it is not a reference.

    Two shapes resolve at run time and so two shapes are read here: the names
    ``variable_name_for`` generates, which carry the ``MCP_`` prefix, and the explicit
    ``{{NAME}}`` placeholder a person can write by hand. The braces and any padding come
    off, because what a deploy has to report is the name the target must supply, not the
    syntax the flow happened to spell it in.

    Recognising any capitalised token instead would fail open on the alphabet of the
    secret: an AWS access key id, or any uppercase hex token, would read as a reference
    and be copied into the flow verbatim.
    """
    if not isinstance(value, str):
        return None
    if PLACEHOLDER_PATTERN.match(value):
        return value.strip("{} \t")
    return value if value.startswith(VARIABLE_PREFIX) else None


def _is_variable_reference(value: str) -> bool:
    """Whether a value is already a reference, so a re-save does not wrap it twice."""
    return variable_reference_name(value) is not None


def project_id_from_mcp_url(url: object, *, base_url: str = "") -> str | None:
    """The Langflow project a server URL points at, or None when it points elsewhere.

    Both kinds of server are deployed the same way: credentials become variables the target
    supplies. One of our own projects also has its address made a variable, because the one it
    was authored with names the plane it was authored on.

    Returns None rather than raising for anything it cannot read, including a URL held in
    a variable: ``{{MCP_SERVER_URL}}`` resolves at run time and names no project now, so
    the caller treats it as external and asks for the variable, which is the safe way to
    be wrong about it.

    **This answers a path question, not a trust question.** Any host can serve this path
    shape, so a match means "names project X" and never "is one of ours". Being wrong asks
    the target for an address it could have been given, which is harmless.
    """
    if not isinstance(url, str):
        return None
    try:
        path = urlparse(url).path
    except ValueError:  # malformed authority, e.g. a bad IPv6 literal
        return None
    match = _PROJECT_MCP_PATH.match(path)
    if match is None and base_url:
        try:
            base_path = urlparse(base_url.strip()).path.rstrip("/")
        except ValueError:
            return None
        match = _PROJECT_MCP_PATH.match(path.removeprefix(base_path))
    return match.group(1).lower() if match else None


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


def mcp_url_variable_name(server_name: str) -> str:
    """The variable a deploy target supplies one of our own projects' address in.

    The key is not a header name, so it cannot land on a variable a header was given.
    """
    return variable_name_for(server_name, "project url")


def url_reads_a_variable(url: object) -> bool:
    """Whether an address is already resolved from a variable where it runs, so it is portable as it stands."""
    return isinstance(url, str) and (
        PLACEHOLDER_PATTERN.match(url) is not None or "{{" in url or url.startswith(VARIABLE_PREFIX)
    )


def project_server_http_config(config: dict[str, Any], *, base_url: str = "") -> dict[str, Any] | None:
    """An entry pointing at a Langflow project as a plain HTTP config, or None for any other entry.

    Auto-install writes these as an ``mcp-proxy`` command with the URL and the headers among its
    arguments. A deploy target cannot start that command, so both are read back out into the shape
    every other server uses. Values are copied as they stand: literal, reference or stored ciphertext.
    """
    url = config.get("url")
    headers = dict(config["headers"]) if isinstance(config.get("headers"), dict) else {}
    args = config.get("args")
    if url is None and isinstance(args, list):
        url = next((item for item in args if project_id_from_mcp_url(item, base_url=base_url) is not None), None)
        for index, item in enumerate(args[:-2]):
            if item == HEADER_ARG_FLAG and isinstance(args[index + 1], str):
                headers[args[index + 1]] = args[index + 2]
    if project_id_from_mcp_url(url, base_url=base_url) is None:
        return None

    http_config = {"url": url}
    if headers:
        http_config["headers"] = headers
    if config.get("url") is not None:
        if config.get("mode") in ("SSE", "Streamable_HTTP"):
            http_config["mode"] = config["mode"]
        for option in ("verify_ssl", "allow_sse_fallback"):
            if isinstance(config.get(option), bool):
                http_config[option] = config[option]
    return http_config


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
    "mcp_url_variable_name",
    "project_id_from_mcp_url",
    "project_server_http_config",
    "strip_config_secrets",
    "url_reads_a_variable",
    "variable_name_for",
    "variable_reference_name",
]
