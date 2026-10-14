"""Keep MCP credentials out of ``flow.data`` when a flow is written.

``flow.data`` is an unencrypted JSON column that travels through export, share and
version history, so a credential stored there is a credential handed to everyone the
flow is handed to. The ``mcp_server`` table is the encrypted home for the same value,
and ``resolve_mcp_config`` already prefers it at runtime, so moving the secret across
costs the flow nothing at run time.

Forward-only by design: flows written before this keep their embedded config and keep
resolving through the same precedence, so no saved flow changes behavior.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from langflow.logging import logger
from langflow.services.auth.mcp_encryption import (
    MCP_CONFIG_VALUE_MASK,
    MCP_SECRET_CONFIG_MAPS,
    decrypt_mcp_config,
    encrypt_mcp_config,
    restore_mcp_config_secrets,
)
from langflow.services.database.lock_retry import is_database_lock_error
from langflow.services.database.models import MCPServer
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.utils.mcp_config_secrets import (
    HEADER_ARG_FLAG,
    NON_SECRET_HEADERS,
    PLACEHOLDER_PATTERN,
    SECRET_CONFIG_FIELDS,
    VARIABLE_PREFIX,
    _is_variable_reference,
    strip_config_secrets,
    variable_name_for,
)

# The constants above are re-exported (unused in this module's own body) so existing
# imports of them from this path keep working now that their definitions moved to
# ``langflow.utils.mcp_config_secrets`` - see that module's docstring for why.
__all__ = [
    "HEADER_ARG_FLAG",
    "NON_SECRET_HEADERS",
    "PLACEHOLDER_PATTERN",
    "SECRET_CONFIG_FIELDS",
    "VARIABLE_PREFIX",
    "MCPSecretTarget",
    "extract_and_strip_mcp_secrets",
    "mcp_server_names",
    "persist_and_strip_mcp_secrets",
    "stage_mcp_secrets",
    "strip_config_secrets",
    "variable_name_for",
]


@dataclass(frozen=True)
class MCPSecretTarget:
    """An originally masked field and its exact scrubbed graph destination."""

    original_config: dict[str, Any]
    target_config: dict[str, Any]
    map_name: str
    key: str


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
    *,
    masked_targets: list[MCPSecretTarget] | None = None,
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
        masked_fields = [
            (map_name, key)
            for map_name in MCP_SECRET_CONFIG_MAPS
            if isinstance(config.get(map_name), dict)
            for key, entry_value in config[map_name].items()
            if entry_value == MCP_CONFIG_VALUE_MASK
        ]
        if not found and not masked_fields:
            continue

        if isinstance(name, str) and name:
            carried.append((name, config))
            if masked_targets is not None:
                masked_targets.extend(
                    MCPSecretTarget(config, stripped, map_name, key) for map_name, key in masked_fields
                )
        elif masked_fields:
            raise HTTPException(status_code=422, detail="A redacted MCP credential requires an existing named server.")
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


def _restore_masked_flow_references(
    original: dict[str, Any],
    resolved_config: dict[str, Any],
    server_name: str,
    targets: list[MCPSecretTarget],
    variables: dict[str, str],
) -> None:
    """Refresh exact masked graph fields with references, never decrypted literals."""
    for target in targets:
        if target.original_config is not original:
            continue
        resolved_values = resolved_config.get(target.map_name)
        target_values = target.target_config.get(target.map_name)
        if (
            not isinstance(resolved_values, dict)
            or not isinstance(target_values, dict)
            or target.key not in resolved_values
        ):
            continue
        # A retry can change a stored reference to a literal, which needs its
        # generated alias again. Neither case changes the original carried mask.
        value = resolved_values[target.key]
        if not isinstance(value, str) or value == MCP_CONFIG_VALUE_MASK:
            raise HTTPException(status_code=422, detail="A redacted MCP credential requires an existing string value.")
        alias = variable_name_for(server_name, target.key)
        if not value or _is_variable_reference(value):
            target_values[target.key] = value
            if variables.get(alias) == MCP_CONFIG_VALUE_MASK:
                del variables[alias]
        else:
            # Management masks cover every map value, even an allowlisted header.
            # A stored credential must not become plaintext in the returned flow.
            target_values[target.key] = alias
            if alias not in variables or variables[alias] == MCP_CONFIG_VALUE_MASK:
                variables[alias] = value


async def stage_mcp_secrets(
    carried: list[tuple[str, dict[str, Any]]],
    variables: dict[str, str],
    user_id: UUID,
    session,
    *,
    rotatable_servers: set[str] | None = None,
    masked_targets: list[MCPSecretTarget] | None = None,
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

    # A flow can carry the management API's masked config. Resolve masks before
    # variable creation or rotation so neither credential store receives a mask.
    resolved_variables = dict(variables)
    resolved_servers: list[tuple[str, dict[str, Any], MCPServer | None]] = []
    for name, config in carried:
        existing = (
            await session.exec(select(MCPServer).where(MCPServer.user_id == user_id, MCPServer.name == name))
        ).first()
        previous = decrypt_mcp_config(existing.config or {}) if existing is not None else None
        try:
            resolved_config = restore_mcp_config_secrets(config, previous)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        _, config_variables, _ = strip_config_secrets(resolved_config, name)
        for variable_name, value in config_variables.items():
            if resolved_variables.get(variable_name) == MCP_CONFIG_VALUE_MASK:
                resolved_variables[variable_name] = value
        _restore_masked_flow_references(config, resolved_config, name, masked_targets or [], resolved_variables)
        resolved_servers.append((name, resolved_config, existing))
    if MCP_CONFIG_VALUE_MASK in resolved_variables.values():
        raise HTTPException(status_code=422, detail="A redacted MCP credential can only preserve an existing value.")

    failed = await _ensure_variables(resolved_variables, user_id, session)
    if failed:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not store an MCP credential securely, so the flow was not saved. "
                "Retry, or set the credential as a global variable and reference it from the server config."
            ),
        )

    for name, config, existing in resolved_servers:
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
    masked_targets: list[MCPSecretTarget] = []
    carried, variables = extract_and_strip_mcp_secrets(flow_data, masked_targets=masked_targets)
    await stage_mcp_secrets(carried, variables, user_id, session, masked_targets=masked_targets)


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
