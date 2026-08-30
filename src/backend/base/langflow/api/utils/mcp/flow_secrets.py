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

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.logging import logger
from langflow.services.auth.mcp_encryption import MCP_SECRET_CONFIG_MAPS, decrypt_mcp_config, encrypt_mcp_config
from langflow.services.database.lock_retry import is_database_lock_error
from langflow.services.database.models import MCPServer
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE

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


def mcp_server_names(flow_data: dict[str, Any] | None) -> set[str]:
    """Names of the MCP servers a flow already references."""
    names: set[str] = set()
    for field in _iter_mcp_server_fields(flow_data):
        value = field.get("value")
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name:
                names.add(name)
    return names


async def stage_mcp_secrets(
    carried: list[tuple[str, dict[str, Any]]],
    variables: dict[str, str],
    user_id: UUID,
    session,
    *,
    rotatable_servers: set[str] | None = None,
) -> None:
    """Stage the carried credential on the caller's session.

    Split from the extraction on purpose. ``run_with_lock_retry`` rolls the session back
    between attempts, which discards the staged rows, while the in-place rewrite of
    ``flow_data`` survives in memory. Re-extracting on attempt 2 therefore finds only the
    reference it wrote itself, stages nothing, and the flow commits pointing at a global
    variable that does not exist. Extract once, stage per attempt.

    Raises when a credential could not be stored securely. Putting the literal back into
    ``flow.data`` instead would answer 200 while writing the secret to an unencrypted
    column that travels through export, share and version history — the caller would never
    learn the protection had been skipped. Refusing the write is visible and recoverable.
    """
    if not carried and not variables:
        return

    failed = await _ensure_variables(variables, user_id, session)
    if failed:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not store an MCP credential securely, so the flow was not saved. "
                "Retry, or set the credential as a global variable and reference it from the server config."
            ),
        )

    for name, config in carried:
        existing = (
            await session.exec(select(MCPServer).where(MCPServer.user_id == user_id, MCPServer.name == name))
        ).first()
        if existing is not None:
            # Rotating here only makes sense when the user is editing a server this flow was
            # already bound to. The row is keyed on (user, name) and shared by every flow of
            # that user, so rotating on any write let one import re-point all of them at
            # whatever credential the file carried, unrecoverably. Only the secret-bearing
            # maps are replaced, so the URL, mode and args maintained here survive.
            if rotatable_servers and name in rotatable_servers:
                _apply_rotated_secrets(existing, config)
            continue
        try:
            async with session.begin_nested():
                session.add(MCPServer(user_id=user_id, name=name, config=encrypt_mcp_config(config)))
        except IntegrityError:
            # Another writer created the same (user, name) first; its row is authoritative.
            await logger.adebug(f"MCP server row '{name}' already exists; keeping the stored config.")
        except Exception as exc:
            if is_database_lock_error(exc):
                raise
            await logger.aerror(f"Could not persist MCP server config carried by a flow: {exc}")


async def persist_and_strip_mcp_secrets(flow_data: dict[str, Any] | None, user_id: UUID, session) -> None:
    """Move any MCP credential in ``flow_data`` into the user's encrypted server rows.

    An existing row is never overwritten: it is the config the user maintains through the
    server manager, and a flow copy is not authoritative over it.

    Nothing is committed here. The rows are staged on the caller's session so they land in
    the same transaction as the flow itself — committing mid-request would break the
    all-or-nothing contract of the batch write path.

    Callers that run inside ``run_with_lock_retry`` must not use this: extract once with
    ``extract_and_strip_mcp_secrets`` outside the loop and call ``stage_mcp_secrets``
    inside each attempt, so a rollback cannot leave the flow referencing a variable that
    was never created.

    A secret carried inside ``args`` (the ``--headers`` triple that auto-install bakes in)
    is dropped rather than referenced, because variables are not resolved inside ``args``.
    Under Langflow the ``mcp_server`` row still serves it; under ``lfx serve`` it is gone.
    """
    carried, variables = extract_and_strip_mcp_secrets(flow_data)
    await stage_mcp_secrets(carried, variables, user_id, session)


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
    except Exception as exc:
        if is_database_lock_error(exc):
            raise
        await logger.awarning(f"Could not list global variables while scrubbing an MCP credential: {exc}")

    failed: set[str] = set()
    for name, value in variables.items():
        if name in existing_names:
            if not await _rotate_variable(variable_service, name, value, user_id, session):
                failed.add(name)
            continue
        try:
            async with session.begin_nested():
                await variable_service.create_variable(
                    user_id=user_id, name=name, value=value, type_=CREDENTIAL_TYPE, session=session
                )
        except Exception as exc:
            # A contended write is transient, not a verdict on this variable. Swallowing it
            # would hand the literal back and save the secret in plaintext; let the caller's
            # retry re-run the whole operation instead.
            if is_database_lock_error(exc):
                raise
            failed.add(name)
            await logger.aerror(f"Could not create global variable '{name}' for an MCP credential: {exc}")
    return failed


def _apply_rotated_secrets(existing: MCPServer, config: dict[str, Any]) -> None:
    """Overwrite only the secret-bearing maps of a stored server config."""
    stored = decrypt_mcp_config(existing.config or {})
    changed = False
    for key in MCP_SECRET_CONFIG_MAPS:
        incoming = config.get(key)
        if isinstance(incoming, dict) and incoming and stored.get(key) != incoming:
            stored[key] = incoming
            changed = True
    if changed:
        existing.config = encrypt_mcp_config(stored)


async def _rotate_variable(variable_service, name: str, value: str, user_id: UUID, session) -> bool:
    """Point an existing variable at the value the flow just carried.

    Returns whether the variable now holds it, so the caller can restore the literal
    rather than save a flow that authenticates with a credential the user replaced.
    """
    try:
        current = await variable_service.get_variable(user_id=user_id, name=name, field="", session=session)
    except Exception:  # noqa: BLE001
        current = None
    if current == value:
        return True
    try:
        async with session.begin_nested():
            await variable_service.update_variable(user_id=user_id, name=name, value=value, session=session)
    except Exception as exc:
        if is_database_lock_error(exc):
            raise
        await logger.aerror(f"Could not rotate global variable '{name}' for an MCP credential: {exc}")
        return False
    return True
