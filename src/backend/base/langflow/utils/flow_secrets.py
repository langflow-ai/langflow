"""Metadata-driven secret-scrubbing helpers for serialized flow data.

This module is deliberately independent of the API and service layers so flow
payloads can be scrubbed at any export boundary without importing FastAPI.
The scrubber removes values identified by field metadata, secret-shaped names,
and credential-bearing URL structure. It cannot prove that an arbitrary value
stored in an otherwise ordinary field is not a secret.
"""

from __future__ import annotations

import re
from copy import deepcopy
from urllib.parse import parse_qsl, urlsplit

API_WORDS = ["api", "key", "token"]

_ASCII_CONTROL_CUTOFF = 0x20
_ASCII_DELETE = 0x7F
_VARIABLE_REFERENCE_MAX_LENGTH = 256

# Per-row override of a table column's ``load_from_db`` flag, written by the
# table cell editor and read by ``lfx.interface.initialize.loading``. Duplicated
# rather than imported to keep this module free of runtime dependencies.
_TABLE_LOAD_FROM_DB_FIELDS = "__load_from_db_fields"

# Defense-in-depth for several widely used credential formats, not an exhaustive
# provider catalog. ``load_from_db`` is the required reference marker, while
# this additional check rejects a matching free-form variable name rather than
# risk packaging a raw credential from inconsistent metadata.
_CREDENTIAL_VALUE_PATTERN = re.compile(
    r"""^(?:
        sk-[A-Za-z0-9_-]{8,}
        | (?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{8,}
        | github_pat_[A-Za-z0-9_]{8,}
        | glpat-[A-Za-z0-9_-]{8,}
        | hf_[A-Za-z0-9]{8,}
        | xox[abps]-[A-Za-z0-9-]{8,}
        | (?:AKIA|ASIA)[0-9A-Z]{16}
    )$""",
    re.VERBOSE,
)

_SECRET_NAME_PARTS = frozenset({"credential", "credentials", "passwd", "password", "secret"})
_SECRET_COMPOUND_NAMES = frozenset(
    {
        "access_key",
        "api_key",
        "apikey",
        "authorization",
        "client_secret",
        "connection_string",
        "cookie",
        "database_uri",
        "database_url",
        "dsn",
        "private_key",
        "proxy_authorization",
        "set_cookie",
    }
)


def has_api_terms(word: str) -> bool:
    """Return whether a field name identifies an API credential."""
    return "api" in word and ("key" in word or ("token" in word and "tokens" not in word))


def remove_api_keys(flow: dict) -> dict:
    """Null legacy password-marked API key fields in a serialized flow."""
    flow_data = flow.get("data")
    if not isinstance(flow_data, dict):
        return flow

    nodes = flow_data.get("nodes")
    if not isinstance(nodes, list):
        return flow

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            continue
        node_inner = node_data.get("node")
        if not isinstance(node_inner, dict):
            continue
        template = node_inner.get("template")
        if not isinstance(template, dict):
            continue
        for value in template.values():
            if not isinstance(value, dict):
                continue
            name = value.get("name")
            if isinstance(name, str) and has_api_terms(name) and value.get("password"):
                value["value"] = None

    return flow


def strip_secret_field_values(flow_data: dict | None) -> dict | None:
    """Return a deep-copied flow-data mapping with persisted secrets removed."""
    # Only ``None`` short-circuits. An empty mapping must still be copied: callers such as
    # ``strip_flow_secrets`` promise the returned ``data`` is detached from the ORM-backed
    # payload, and returning the original ``{}`` would alias it.
    if flow_data is None:
        return flow_data
    return strip_secret_field_values_in_place(deepcopy(flow_data))


def strip_flow_secrets(flow: dict) -> dict:
    """Return a copy of a serialized flow *envelope* with persisted secrets removed.

    ``strip_secret_field_values`` scrubs a bare flow-data mapping; export paths
    hold the surrounding flow dict (``{"name": ..., "data": {...}}``) instead.
    This wrapper keeps those call sites on the metadata-driven scrubber rather
    than the legacy :func:`remove_api_keys`, which only nulled fields that were
    both ``password``-marked *and* named like an API key.

    The returned envelope is a shallow copy whose ``data`` is detached, so the
    caller never mutates the ORM-backed payload it serialized from.
    """
    if not isinstance(flow, dict) or "data" not in flow:
        return flow
    scrubbed = dict(flow)
    scrubbed["data"] = strip_secret_field_values(flow["data"])
    return scrubbed


def _normalized_secret_name(value: object) -> str:
    """Normalize snake, kebab, and camel-case names for classification."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or ""))
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()


def _is_secret_name(value: object) -> bool:
    normalized = _normalized_secret_name(value)
    if normalized in _SECRET_COMPOUND_NAMES:
        return True
    parts = set(normalized.split("_"))
    is_token_value = normalized == "token" or normalized.endswith("_token")
    return bool(parts & _SECRET_NAME_PARTS) or is_token_value or {"api", "key"}.issubset(parts)


def _is_variable_reference(value: object) -> bool:
    """Return whether a ``load_from_db`` value looks like a global-variable name.

    A bound field stores the referenced variable's *name* in ``value``, not the
    secret itself. Values that cannot be a name — empty, oversized, control
    characters, a non-string, a URL carrying credentials, or a token issued
    under a well-known credential prefix — are treated as raw secrets instead.

    Variable names are freeform, so this check narrows the blast radius of a
    mislabelled field rather than eliminating it: a secret whose text is shaped
    like an ordinary name is indistinguishable from a real reference here, and
    a legitimate name shaped like a known credential is rejected fail-closed.
    The primary signal is the ``load_from_db`` metadata, which the editor keeps
    in step with whether a value is a name or a literal; these additional shape
    checks deliberately fail closed when that metadata and the value disagree.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    if len(value) > _VARIABLE_REFERENCE_MAX_LENGTH:
        return False
    if any(ord(character) < _ASCII_CONTROL_CUTOFF or ord(character) == _ASCII_DELETE for character in value):
        return False
    if _CREDENTIAL_VALUE_PATTERN.match(value.strip()):
        return False
    return not _contains_url_credentials(value)


def _contains_url_credentials(value: str) -> bool:
    """Return whether a URL contains userinfo or secret-named parameters."""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    if parsed.username is not None or parsed.password is not None:
        return True
    return any(
        _is_secret_name(key)
        for component in (parsed.query, parsed.fragment)
        for key, _ in parse_qsl(component, keep_blank_values=True)
    )


def _structured_container_frame(value: object):
    """Prepare one mutable container for bounded, in-place traversal."""
    if isinstance(value, dict):
        discriminator = next(
            (value.get(key) for key in ("key", "name", "header") if _is_secret_name(value.get(key))),
            None,
        )
        if discriminator is not None and "value" in value:
            value["value"] = None
        return value, iter(value), True
    if isinstance(value, list):
        return value, iter(range(len(value))), False
    return None


def _strip_structured_secret_values_in_place(value: object) -> object:
    """Iteratively null secret-named values without copying wide subtrees."""
    if isinstance(value, str) and _contains_url_credentials(value):
        return None
    root_frame = _structured_container_frame(value)
    if root_frame is None:
        return value

    frames = [root_frame]
    while frames:
        container, keys, classify_keys = frames[-1]
        try:
            key = next(keys)
        except StopIteration:
            frames.pop()
            continue

        if classify_keys and _is_secret_name(key):
            container[key] = None
            continue
        nested_value = container[key]
        if isinstance(nested_value, str) and _contains_url_credentials(nested_value):
            container[key] = None
            continue
        nested_frame = _structured_container_frame(nested_value)
        if nested_frame is not None:
            frames.append(nested_frame)
    return value


def _cell_loads_from_db(row_metadata: object, column: str) -> bool | None:
    """Return one row's explicit ``load_from_db`` choice for a column.

    Mirrors ``cell_load_from_db`` in ``lfx.interface.initialize.loading``: a row
    may override its schema column per cell, so the two must agree on which
    cells resolve to a variable and which hold a literal. ``None`` means the row
    records no choice, which the runtime resolves from the database.
    """
    if isinstance(row_metadata, dict):
        return bool(row_metadata[column]) if column in row_metadata else None
    if isinstance(row_metadata, list):
        return column in row_metadata
    return None


def _table_reference_columns(field: dict) -> frozenset[str]:
    """Return table columns whose cells hold global-variable name references."""
    schema = field.get("table_schema")
    if not isinstance(schema, list):
        return frozenset()
    return frozenset(
        column["name"]
        for column in schema
        if isinstance(column, dict) and column.get("load_from_db") and isinstance(column.get("name"), str)
    )


def _strip_table_rows_in_place(field: dict, reference_columns: frozenset[str], variable_references: set[str]) -> None:
    """Strip table rows while preserving valid ``load_from_db`` column references."""
    rows = field.get("value")
    if not isinstance(rows, list):
        field["value"] = _strip_structured_secret_values_in_place(rows)
        return
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            rows[index] = _strip_structured_secret_values_in_place(row)
            continue
        # Detach the per-cell metadata so the generic scrub cannot null an entry
        # keyed by a secret-named column and silently turn a reference cell into
        # a literal one for the deployment target.
        row_metadata = row.pop(_TABLE_LOAD_FROM_DB_FIELDS, None)
        preserved: dict[str, str | None] = {}
        for column in reference_columns & row.keys():
            cell = row[column]
            # Only a cell the runtime resolves from the database holds a
            # variable *name*. A cell the row marks as not loading from the
            # database holds the literal value itself, so it is scrubbed like
            # any other secret rather than published as a required variable.
            if _cell_loads_from_db(row_metadata, column) is False or not _is_variable_reference(cell):
                preserved[column] = None
                continue
            variable_references.add(cell)
            preserved[column] = cell
        _strip_structured_secret_values_in_place(row)
        row.update(preserved)
        if row_metadata is not None:
            row[_TABLE_LOAD_FROM_DB_FIELDS] = row_metadata


def _strip_template_field_value(field: dict, variable_references: set[str] | None = None) -> None:
    """Strip a template field according to metadata and value shape."""
    if (
        variable_references is not None
        and field.get("load_from_db")
        and not isinstance(field.get("value"), (dict, list))
    ):
        # A bound field stores the global-variable *name*, not the secret, so a
        # deployment target can re-resolve the credential it provisions under
        # that name. Anything that fails the reference shape check is nulled.
        value = field.get("value")
        if _is_variable_reference(value):
            variable_references.add(value)
        else:
            field["value"] = None
        return

    if field.get("password") or _is_secret_name(field.get("name")):
        field["value"] = None
        return

    field_type = str(field.get("type") or "").lower()
    input_type = str(field.get("_input_type") or "").lower()
    if field_type == "mcp" or input_type == "mcpinput":
        value = field.get("value")
        name = value.get("name") if isinstance(value, dict) else None
        field["value"] = {"name": name} if name else None
        return

    if variable_references is not None:
        reference_columns = _table_reference_columns(field)
        if reference_columns:
            _strip_table_rows_in_place(field, reference_columns, variable_references)
            return

    field["value"] = _strip_structured_secret_values_in_place(field.get("value"))


def _strip_secrets_from_nodes(nodes: list, variable_references: set[str] | None = None) -> None:
    """Iteratively strip secret values from regular and grouped flow nodes."""
    node_frames = [iter(nodes)]
    while node_frames:
        try:
            node = next(node_frames[-1])
        except StopIteration:
            node_frames.pop()
            continue
        if not isinstance(node, dict):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            continue
        node_inner = node_data.get("node")
        if not isinstance(node_inner, dict):
            continue
        template = node_inner.get("template")
        if isinstance(template, dict):
            for value in template.values():
                if isinstance(value, dict):
                    _strip_template_field_value(value, variable_references)

        flow = node_inner.get("flow")
        if isinstance(flow, dict):
            nested_flow_data = flow.get("data")
            if isinstance(nested_flow_data, dict):
                nested_nodes = nested_flow_data.get("nodes")
                if isinstance(nested_nodes, list):
                    node_frames.append(iter(nested_nodes))


def strip_secret_field_values_in_place(
    flow_data: dict | None,
    *,
    variable_references: set[str] | None = None,
) -> dict | None:
    """Scrub a detached flow-data mapping in place with bounded traversal memory.

    By default every secret-bearing value is nulled, including the names of
    global variables bound via ``load_from_db`` — the right contract for
    anonymous consumers such as the public-flow endpoint. Deployment packaging
    passes ``variable_references``: fields (and table cells) that the runtime
    resolves from the database then keep their variable-*name* values, and
    every preserved name is added to the set so the caller can emit a
    required-variables manifest.

    Only values the runtime would look up are preserved — a table cell the row
    marks as not loading from the database holds the literal secret, so it is
    nulled like any other. Values that cannot be a variable name are nulled
    too, but that shape check narrows rather than closes the gap: a flow whose
    ``load_from_db`` metadata is wrong can still carry a raw secret shaped like
    an ordinary name.
    """
    if not flow_data:
        return flow_data
    nodes = flow_data.get("nodes")
    if isinstance(nodes, list):
        _strip_secrets_from_nodes(nodes, variable_references)
    return flow_data


__all__ = [
    "API_WORDS",
    "has_api_terms",
    "remove_api_keys",
    "strip_flow_secrets",
    "strip_secret_field_values",
    "strip_secret_field_values_in_place",
]
