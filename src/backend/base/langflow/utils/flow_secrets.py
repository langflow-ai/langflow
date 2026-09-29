"""Metadata-driven secret-scrubbing helpers for serialized flow data.

This module is deliberately independent of the API and service layers so flow
payloads can be scrubbed at any export boundary without importing FastAPI.
The scrubber removes values identified by field metadata, secret-shaped names,
and credential-bearing URL structure. It cannot prove that an arbitrary value
stored in an otherwise ordinary field is not a secret.
"""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlsplit

if TYPE_CHECKING:
    from collections.abc import Collection

API_WORDS = ["api", "key", "token"]

_ASCII_CONTROL_CUTOFF = 0x20
_ASCII_DELETE = 0x7F
_VARIABLE_REFERENCE_MAX_LENGTH = 256

# Per-row override of a table column's ``load_from_db`` flag, written by the
# table cell editor and read by ``lfx.interface.initialize.loading``. Duplicated
# rather than imported to keep this module free of runtime dependencies.
_TABLE_LOAD_FROM_DB_FIELDS = "__load_from_db_fields"
_HIDDEN_VALUE_METADATA_KEYS = frozenset(
    {"id", "key", "name", "header", "password", "load_from_db", "type", "_input_type", _TABLE_LOAD_FROM_DB_FIELDS}
)
_CANVAS_LAYOUT_KEYS = frozenset(
    {
        "position",
        "positionAbsolute",
        "width",
        "height",
        "selected",
        "dragging",
        "measured",
        "sourcePosition",
        "targetPosition",
        "style",
    }
)

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


class HiddenFieldMetadataError(ValueError):
    """A shared graph changed metadata used to hide an owner's value."""


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
    # Only ``None`` short-circuits. An empty mapping must still be copied: callers promise
    # the returned data is detached from the ORM-backed payload, and returning the
    # original ``{}`` would alias it.
    if flow_data is None:
        return flow_data
    return strip_secret_field_values_in_place(deepcopy(flow_data))


def restore_redacted_flow_values(incoming_data: dict, stored_data: dict | None) -> dict:
    """Restore hidden values in a shared editor's detached graph for save or run.

    A non-owner receives a scrubbed flow and may send that graph back for an
    edit. Restore only null values that the read scrubber hid
    in the same stored node and template field. The metadata that classified
    a hidden value must still match the stored field. A non-null edit remains
    the editor's own value. If an owner's value is restored, the executable
    graph must remain unchanged: other inputs can redirect or return the key.
    """
    restored = deepcopy(incoming_data)
    if not isinstance(stored_data, dict):
        return restored
    redacted_data = strip_secret_field_values(stored_data)
    if not isinstance(redacted_data, dict):
        return restored

    restored_hidden_value_anywhere = False
    node_frames = [(restored.get("nodes"), stored_data.get("nodes"), redacted_data.get("nodes"))]
    while node_frames:
        incoming_nodes, stored_nodes, redacted_nodes = node_frames.pop()
        if not all(isinstance(nodes, list) for nodes in (incoming_nodes, stored_nodes, redacted_nodes)):
            continue
        incoming_ids = Counter(
            node.get("id") for node in incoming_nodes if isinstance(node, dict) and isinstance(node.get("id"), str)
        )
        stored_ids = Counter(
            node.get("id") for node in stored_nodes if isinstance(node, dict) and isinstance(node.get("id"), str)
        )
        redacted_stored_ids = {
            stored_node.get("id")
            for stored_node, redacted_node in zip(stored_nodes, redacted_nodes, strict=False)
            if isinstance(stored_node, dict)
            and isinstance(redacted_node, dict)
            and stored_node != redacted_node
            and isinstance(stored_node.get("id"), str)
        }
        stored_by_id = {
            node["id"]: node
            for node in stored_nodes
            if isinstance(node, dict) and isinstance(node.get("id"), str) and stored_ids[node["id"]] == 1
        }
        redacted_by_id = {
            node["id"]: node for node in redacted_nodes if isinstance(node, dict) and isinstance(node.get("id"), str)
        }
        for incoming_node in incoming_nodes:
            if not isinstance(incoming_node, dict):
                continue
            node_id = incoming_node.get("id")
            if not isinstance(node_id, str):
                continue
            if incoming_ids[node_id] != 1 or stored_ids[node_id] > 1:
                if node_id in redacted_stored_ids:
                    raise HiddenFieldMetadataError
                continue
            stored_node = stored_by_id.get(node_id)
            redacted_node = redacted_by_id.get(node_id)
            if stored_node is None or redacted_node is None:
                continue
            if stored_node != redacted_node and incoming_node.get("type") != stored_node.get("type"):
                raise HiddenFieldMetadataError
            incoming_inner = _node_inner(incoming_node)
            stored_inner = _node_inner(stored_node)
            redacted_inner = _node_inner(redacted_node)
            if not all(isinstance(inner, dict) for inner in (incoming_inner, stored_inner, redacted_inner)):
                if stored_node != redacted_node:
                    raise HiddenFieldMetadataError
                continue
            if stored_inner != redacted_inner and incoming_inner.get("type") != stored_inner.get("type"):
                raise HiddenFieldMetadataError
            incoming_template = incoming_inner.get("template")
            stored_template = stored_inner.get("template")
            redacted_template = redacted_inner.get("template")
            if stored_template != redacted_template and not isinstance(incoming_template, dict):
                raise HiddenFieldMetadataError
            if all(isinstance(template, dict) for template in (incoming_template, stored_template, redacted_template)):
                restored_hidden_value = False
                for field_name in stored_template.keys() - incoming_template.keys():
                    if stored_template[field_name] != redacted_template.get(field_name):
                        raise HiddenFieldMetadataError
                for field_name, incoming_field in incoming_template.items():
                    stored_field = stored_template.get(field_name)
                    redacted_field = redacted_template.get(field_name)
                    if not all(isinstance(field, dict) for field in (incoming_field, stored_field, redacted_field)):
                        continue
                    if "value" in incoming_field and "value" in stored_field and "value" in redacted_field:
                        if _frontend_cleared_hidden_binding(incoming_field, stored_field, redacted_field):
                            # A shared canvas receives a null variable name, then its
                            # missing-variable hook may clear the binding to "".
                            # Preserve the owner's binding for a layout-only save.
                            incoming_template[field_name] = deepcopy(stored_field)
                            restored_hidden_value = True
                            continue
                        before_restore = deepcopy(incoming_field["value"])
                        restored_value = _restore_redacted_value(
                            incoming_field["value"], stored_field["value"], redacted_field["value"]
                        )
                        if restored_value != before_restore and {
                            key: value for key, value in incoming_field.items() if key != "value"
                        } != {key: value for key, value in stored_field.items() if key != "value"}:
                            raise HiddenFieldMetadataError
                        restored_hidden_value |= restored_value != before_restore
                        incoming_field["value"] = restored_value
                restored_hidden_value_anywhere |= restored_hidden_value

            incoming_flow = incoming_inner.get("flow")
            stored_flow = stored_inner.get("flow")
            redacted_flow = redacted_inner.get("flow")
            if stored_flow != redacted_flow and not isinstance(incoming_flow, dict):
                raise HiddenFieldMetadataError
            if all(isinstance(flow, dict) for flow in (incoming_flow, stored_flow, redacted_flow)):
                incoming_nested = incoming_flow.get("data")
                stored_nested = stored_flow.get("data")
                redacted_nested = redacted_flow.get("data")
                if stored_nested != redacted_nested and not isinstance(incoming_nested, dict):
                    raise HiddenFieldMetadataError
                if all(isinstance(data, dict) for data in (incoming_nested, stored_nested, redacted_nested)):
                    node_frames.append(
                        (incoming_nested.get("nodes"), stored_nested.get("nodes"), redacted_nested.get("nodes"))
                    )
    if restored_hidden_value_anywhere:
        _ensure_shared_graph_execution_unchanged(restored, stored_data)
    return restored


def _node_inner(node: dict) -> dict | None:
    node_data = node.get("data")
    inner = node_data.get("node") if isinstance(node_data, dict) else None
    return inner if isinstance(inner, dict) else None


def _frontend_cleared_hidden_binding(incoming: dict, stored: dict, redacted: dict) -> bool:
    """Recognize the UI's empty-value cleanup of a hidden variable reference."""
    return (
        stored.get("load_from_db") is True
        and incoming.get("load_from_db") is False
        and stored.get("value") != redacted.get("value")
        and redacted.get("value") is None
        and incoming.get("value") == ""
        and {key: value for key, value in incoming.items() if key not in {"value", "load_from_db"}}
        == {key: value for key, value in stored.items() if key not in {"value", "load_from_db"}}
    )


def _restore_redacted_value(incoming: object, stored: object, redacted: object) -> object:
    """Copy just the leaves removed by the read scrubber into an incoming value."""
    if incoming is None:
        return deepcopy(stored) if redacted is None else None
    if isinstance(incoming, dict) and isinstance(stored, dict) and isinstance(redacted, dict):
        if stored != redacted:
            for key in (stored.keys() & redacted.keys()) - incoming.keys():
                if stored[key] != redacted[key]:
                    raise HiddenFieldMetadataError
        before_restore = deepcopy(incoming)
        for key in incoming.keys() & stored.keys() & redacted.keys():
            incoming[key] = _restore_redacted_value(incoming[key], stored[key], redacted[key])
        if stored != redacted and incoming != before_restore:
            metadata_keys = _HIDDEN_VALUE_METADATA_KEYS & (stored.keys() | incoming.keys())
            for key in metadata_keys:
                if key not in incoming or key not in stored or incoming[key] != stored[key]:
                    raise HiddenFieldMetadataError
    elif isinstance(incoming, list) and isinstance(stored, list) and isinstance(redacted, list):
        stored_keys = Counter(_structured_row_identity(item) for item in stored)
        incoming_keys = Counter(_structured_row_identity(item) for item in incoming)
        stored_by_key = {
            key: index
            for index, item in enumerate(stored)
            if (key := _structured_row_identity(item)) is not None and stored_keys[key] == 1
        }
        for index, incoming_item in enumerate(incoming):
            key = _structured_row_identity(incoming_item)
            if key is not None:
                # Reordered rows can keep their own values; duplicate row
                # identifiers must never inherit a different row's credential.
                if incoming_keys[key] != 1 or key not in stored_by_key:
                    if any(
                        _structured_row_identity(stored_item) == key and stored_item != redacted_item
                        for stored_item, redacted_item in zip(stored, redacted, strict=False)
                    ):
                        raise HiddenFieldMetadataError
                    continue
                stored_index = stored_by_key[key]
            else:
                if index >= len(stored):
                    continue
                if incoming_item != redacted[index]:
                    if stored[index] != redacted[index] and (len(stored) != 1 or len(incoming) != 1):
                        # Without an identifier, a changed row can only be
                        # matched safely when it is the sole row in the list.
                        raise HiddenFieldMetadataError
                    if stored[index] == redacted[index]:
                        continue
                stored_index = index
            incoming[index] = _restore_redacted_value(incoming_item, stored[stored_index], redacted[stored_index])
    return incoming


def _structured_row_identity(value: object) -> tuple[str, str] | None:
    if isinstance(value, dict):
        for key in ("id", "key", "name", "header"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return key, candidate
    return None


def _ensure_shared_graph_execution_unchanged(incoming_data: dict, stored_data: dict) -> None:
    """Allow canvas layout edits while keeping a restored-key graph executable as stored."""
    if {key: value for key, value in incoming_data.items() if key not in {"nodes", "viewport"}} != {
        key: value for key, value in stored_data.items() if key not in {"nodes", "viewport"}
    }:
        raise HiddenFieldMetadataError
    incoming_nodes = incoming_data.get("nodes")
    stored_nodes = stored_data.get("nodes")
    if not isinstance(incoming_nodes, list) or not isinstance(stored_nodes, list):
        raise HiddenFieldMetadataError
    if any(
        not isinstance(node, dict) or not isinstance(node.get("id"), str) for node in (*incoming_nodes, *stored_nodes)
    ):
        raise HiddenFieldMetadataError
    incoming_by_id = {node["id"]: node for node in incoming_nodes}
    stored_by_id = {node["id"]: node for node in stored_nodes}
    if (
        len(incoming_by_id) != len(incoming_nodes)
        or len(stored_by_id) != len(stored_nodes)
        or incoming_by_id.keys() != stored_by_id.keys()
    ):
        raise HiddenFieldMetadataError
    for node_id, incoming_node in incoming_by_id.items():
        stored_node = stored_by_id[node_id]
        if {key: value for key, value in incoming_node.items() if key not in _CANVAS_LAYOUT_KEYS} != {
            key: value for key, value in stored_node.items() if key not in _CANVAS_LAYOUT_KEYS
        }:
            raise HiddenFieldMetadataError


def strip_flow_secrets(flow: dict, *, known_variable_names: Collection[str] = frozenset()) -> dict:
    """Return a copy of a serialized flow *envelope* with persisted secrets removed.

    ``strip_secret_field_values`` scrubs a bare flow-data mapping; export paths
    hold the surrounding flow dict (``{"name": ..., "data": {...}}``) instead.
    This wrapper keeps those call sites on the metadata-driven scrubber rather
    than the legacy :func:`remove_api_keys`, which only nulled fields that were
    both ``password``-marked *and* named like an API key.

    Fields bound to a global variable (``load_from_db``) keep the variable
    *name*, not the secret, so the importing instance can resolve the
    credential by that name. A bound value is kept only when it names one of
    ``known_variable_names`` (the flow owner's existing global variables), so a
    literal secret behind a stale ``load_from_db`` flag is nulled even when it
    is shaped like a name. The empty default nulls every bound value.

    The returned envelope is a shallow copy whose ``data`` is detached, so the
    caller never mutates the ORM-backed payload it serialized from.
    """
    if not isinstance(flow, dict) or "data" not in flow:
        return flow
    scrubbed = dict(flow)
    scrubbed["data"] = strip_secret_field_values_in_place(
        deepcopy(flow["data"]),
        variable_references=set(),
        known_variable_names=known_variable_names,
    )
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


def _is_preserved_reference(value: object, known_variable_names: Collection[str] | None) -> bool:
    """Return whether a ``load_from_db`` value is kept as a variable-name reference.

    ``known_variable_names`` restricts preserved values to names of existing
    global variables. ``None`` keeps every value that passes the shape check.
    """
    if not _is_variable_reference(value):
        return False
    return known_variable_names is None or value in known_variable_names


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


def _strip_table_rows_in_place(
    field: dict,
    reference_columns: frozenset[str],
    variable_references: set[str],
    known_variable_names: Collection[str] | None = None,
) -> None:
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
            if _cell_loads_from_db(row_metadata, column) is False or not _is_preserved_reference(
                cell, known_variable_names
            ):
                preserved[column] = None
                continue
            variable_references.add(cell)
            preserved[column] = cell
        _strip_structured_secret_values_in_place(row)
        row.update(preserved)
        if row_metadata is not None:
            row[_TABLE_LOAD_FROM_DB_FIELDS] = row_metadata


def _strip_template_field_value(
    field: dict,
    variable_references: set[str] | None = None,
    known_variable_names: Collection[str] | None = None,
) -> None:
    """Strip a template field according to metadata and value shape."""
    if (
        variable_references is not None
        and field.get("load_from_db")
        and not isinstance(field.get("value"), (dict, list))
    ):
        # A bound field stores the global-variable *name*, not the secret, so a
        # deployment target can re-resolve the credential it provisions under
        # that name. Anything that fails the reference shape check, or names no
        # variable in ``known_variable_names`` when the caller passes it, is nulled.
        value = field.get("value")
        if _is_preserved_reference(value, known_variable_names):
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

    reference_columns = _table_reference_columns(field)
    if reference_columns:
        # A shared read has no variable manifest. Even an ordinary-looking
        # column name can hold the owner's variable name, so hide every bound
        # cell rather than relying on the column's spelling to classify it.
        _strip_table_rows_in_place(
            field,
            reference_columns,
            variable_references if variable_references is not None else set(),
            known_variable_names if variable_references is not None else frozenset(),
        )
        return

    field["value"] = _strip_structured_secret_values_in_place(field.get("value"))


def _strip_secrets_from_nodes(
    nodes: list,
    variable_references: set[str] | None = None,
    known_variable_names: Collection[str] | None = None,
) -> None:
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
                    _strip_template_field_value(value, variable_references, known_variable_names)

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
    known_variable_names: Collection[str] | None = None,
) -> dict | None:
    """Scrub a detached flow-data mapping in place with bounded traversal memory.

    By default every secret-bearing value is nulled, including the names of
    global variables bound via ``load_from_db`` — the right contract for
    anonymous consumers such as the public-flow endpoint. Deployment packaging
    and flow/project export pass ``variable_references``: fields (and table
    cells) that the runtime resolves from the database then keep their
    variable-*name* values, and every preserved name is added to the set so the
    caller can emit a required-variables manifest.

    Only values the runtime would look up are preserved — a table cell the row
    marks as not loading from the database holds the literal secret, so it is
    nulled like any other. Values that cannot be a variable name are nulled
    too, but that shape check narrows rather than closes the gap: a flow whose
    ``load_from_db`` metadata is wrong can still carry a raw secret shaped like
    an ordinary name. Callers that can list the owner's global variables pass
    ``known_variable_names`` to close it: only values naming one of those
    variables are then preserved.
    """
    if not flow_data:
        return flow_data
    nodes = flow_data.get("nodes")
    if isinstance(nodes, list):
        _strip_secrets_from_nodes(nodes, variable_references, known_variable_names)
    return flow_data


__all__ = [
    "API_WORDS",
    "HiddenFieldMetadataError",
    "has_api_terms",
    "remove_api_keys",
    "strip_flow_secrets",
    "strip_secret_field_values",
    "strip_secret_field_values_in_place",
]
