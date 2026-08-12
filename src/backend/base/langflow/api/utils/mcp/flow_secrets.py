"""Keep MCP credentials out of ``flow.data`` when a flow is written.

``flow.data`` is an unencrypted JSON column that travels through export, share and
version history, so a credential stored there is a credential handed to everyone the
flow is handed to. The ``mcp_server`` table is the encrypted home for the same value,
and ``resolve_mcp_config`` already prefers it at runtime, so moving the secret across
costs the flow nothing at run time.

Forward-only by design: flows written before this keep their embedded config and keep
resolving through the same precedence, so no saved flow changes behavior.
"""

import hashlib
import re
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.logging import logger
from langflow.services.auth.mcp_encryption import MCP_SECRET_CONFIG_MAPS, encrypt_mcp_config
from langflow.services.database.models import MCPServer
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE

SECRET_CONFIG_FIELDS = ("api_key", "apiKey", "authorization", "Authorization")

HEADER_ARG_FLAG = "--headers"

VARIABLE_PREFIX = "MCP_"

PLACEHOLDER_PATTERN = re.compile(r"^\{\{\s*[A-Za-z_][A-Za-z0-9_\-]*\s*\}\}$")


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
                if isinstance(entry_value, str) and entry_value and not _is_variable_reference(entry_value):
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


def _iter_mcp_server_fields(flow_data: dict[str, Any] | None):
    """Yield every ``mcp_server`` template field of a flow, nested subflows included."""
    if not isinstance(flow_data, dict):
        return
    frames = [iter(flow_data.get("nodes") or [])]
    while frames:
        try:
            node = next(frames[-1])
        except StopIteration:
            frames.pop()
            continue
        if not isinstance(node, dict):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            continue
        inner = node_data.get("node")
        if not isinstance(inner, dict):
            continue

        template = inner.get("template")
        if isinstance(template, dict):
            field = template.get("mcp_server")
            if isinstance(field, dict):
                yield field

        nested = inner.get("flow")
        if isinstance(nested, dict):
            nested_data = nested.get("data")
            if isinstance(nested_data, dict) and isinstance(nested_data.get("nodes"), list):
                frames.append(iter(nested_data["nodes"]))


def extract_and_strip_mcp_secrets(
    flow_data: dict[str, Any] | None,
) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, str]]:
    """Strip MCP secrets from ``flow_data`` in place, returning what has to be stored instead.

    Each entry is the server name and the *original* config, so the caller can persist a
    runnable config while the flow keeps only what is safe to hand around.
    """
    carried: list[tuple[str, dict[str, Any]]] = []
    variables: dict[str, str] = {}

    for field in _iter_mcp_server_fields(flow_data):
        value = field.get("value")
        if not isinstance(value, dict):
            continue
        config = value.get("config")
        if not isinstance(config, dict):
            continue

        name = value.get("name")
        server_name = name if isinstance(name, str) and name else "server"

        stripped, config_variables, found = strip_config_secrets(config, server_name)
        if not found:
            continue

        if isinstance(name, str) and name:
            carried.append((name, config))
        variables.update(config_variables)
        value["config"] = stripped

    return carried, variables


def _restore_unresolvable_references(
    flow_data: dict[str, Any] | None, variables: dict[str, str], failed: set[str]
) -> None:
    """Put a literal back when its variable could not be created.

    Stripping a credential the runtime can no longer resolve trades a leak for a broken
    flow the caller was told was saved. Secrecy is not worth a silent outage, so an entry
    whose variable failed goes back the way the caller sent it.
    """
    if not failed:
        return
    for field in _iter_mcp_server_fields(flow_data):
        value = field.get("value")
        if not isinstance(value, dict):
            continue
        config = value.get("config")
        if not isinstance(config, dict):
            continue
        for key in MCP_SECRET_CONFIG_MAPS:
            entries = config.get(key)
            if not isinstance(entries, dict):
                continue
            for entry_key, entry_value in entries.items():
                if entry_value in failed:
                    entries[entry_key] = variables[entry_value]


async def persist_and_strip_mcp_secrets(flow_data: dict[str, Any] | None, user_id: UUID, session) -> None:
    """Move any MCP credential in ``flow_data`` into the user's encrypted server rows.

    An existing row is never overwritten: it is the config the user maintains through the
    server manager, and a flow copy is not authoritative over it.

    Nothing is committed here. The rows are staged on the caller's session so they land in
    the same transaction as the flow itself — committing mid-request would break the
    all-or-nothing contract of the batch write path and would survive a lock retry that
    the caller expects to be re-runnable from a clean state.

    A secret carried inside ``args`` (the ``--headers`` triple that auto-install bakes in)
    is dropped rather than referenced, because variables are not resolved inside ``args``.
    Under Langflow the ``mcp_server`` row still serves it; under ``lfx serve`` it is gone.
    """
    carried, variables = extract_and_strip_mcp_secrets(flow_data)
    if not carried and not variables:
        return

    failed = await _ensure_variables(variables, user_id, session)
    _restore_unresolvable_references(flow_data, variables, failed)

    for name, config in carried:
        existing = (
            await session.exec(select(MCPServer).where(MCPServer.user_id == user_id, MCPServer.name == name))
        ).first()
        if existing is not None:
            continue
        try:
            async with session.begin_nested():
                session.add(MCPServer(user_id=user_id, name=name, config=encrypt_mcp_config(config)))
        except IntegrityError:
            # Another writer created the same (user, name) first; its row is authoritative.
            await logger.adebug(f"MCP server row '{name}' already exists; keeping the stored config.")
        except Exception as exc:  # noqa: BLE001
            await logger.aerror(f"Could not persist MCP server config carried by a flow: {exc}")


async def _ensure_variables(variables: dict[str, str], user_id: UUID, session) -> set[str]:
    """Create the referenced global variables so the rewritten config resolves.

    Existing names are left alone: the value the user maintains outranks a copy that
    happened to be sitting in a flow. Returns the names that could not be created, so the
    caller can put those literals back instead of saving a flow that cannot authenticate.
    """
    if not variables:
        return set()

    variable_service = get_variable_service()
    existing_names = set()
    try:
        existing_names = set(await variable_service.list_variables(user_id, session))
    except Exception as exc:  # noqa: BLE001
        await logger.awarning(f"Could not list global variables while scrubbing an MCP credential: {exc}")

    failed: set[str] = set()
    for name, value in variables.items():
        if name in existing_names:
            continue
        try:
            async with session.begin_nested():
                await variable_service.create_variable(
                    user_id=user_id, name=name, value=value, type_=CREDENTIAL_TYPE, session=session
                )
        except Exception as exc:  # noqa: BLE001
            failed.add(name)
            await logger.aerror(f"Could not create global variable '{name}' for an MCP credential: {exc}")
    return failed
