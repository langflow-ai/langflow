"""Find the stored files a flow's components read.

A deploy has to carry a project's documents into the environment that will serve it, and
this is the list that drives it. Getting it wrong is expensive in a particular way: a file
left out is not noticed at deploy time but when someone runs the flow and a component
cannot open its input, so the scan reports what it could not resolve rather than dropping it.

A ``FileInput`` holds one of three things, and only the first can be copied:

* a storage key, ``<namespace>/<file name>``, where the namespace is the uploading user's id
  or a flow's id — the form both storage backends address
* an absolute path on the machine the editor runs on, which the target cannot resolve
* a bare file name, which names nothing on its own

The second and third are returned as unresolved, with the node and field that hold them, so
a person can be told which component to fix.

This reads serialized flow data and nothing else: no database, no storage, no API. Whether
each key's bytes actually exist is a separate question, asked of storage later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field

from lfx.services.storage.namespace import validate_namespace

# ``_canonical_file_input`` is set at run time by the graph to mark a field whose ``value``
# is the file path. It is not in stored flow data, so the scan reads ``file_path`` and then
# ``value`` for every file field rather than relying on it.
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[/\\]")


@dataclass(frozen=True)
class UnresolvedFile:
    """A file field whose value is not a storage key, and where it sits."""

    value: str
    reason: str
    node_id: str
    field_name: str


@dataclass
class FlowFiles:
    """Every stored file a flow addresses, and every reference that is not one."""

    keys: list[str] = dataclass_field(default_factory=list)
    unresolved: list[UnresolvedFile] = dataclass_field(default_factory=list)


def collect_flow_files(flow_data: dict | None) -> FlowFiles:
    """The storage keys a flow's file inputs name, with whatever could not be resolved.

    Keys are deduplicated and sorted, so two components sharing one document produce one
    entry and the result is stable enough to compare between two runs. Nested flows are
    walked as well: a node can embed another flow's data, and its components read files too.
    """
    result = FlowFiles()
    seen: dict[str, None] = {}
    for node_id, field_name, value in _file_field_values(flow_data):
        reason = _why_not_a_key(value)
        if reason is not None:
            result.unresolved.append(UnresolvedFile(value=value, reason=reason, node_id=node_id, field_name=field_name))
            continue
        namespace, _, file_name = value.partition("/")
        seen.setdefault(f"{validate_namespace(namespace)}/{file_name}", None)
    result.keys = sorted(seen)
    return result


class FileKeyCollisionError(ValueError):
    """Two different stored files would land on the same key in the serving environment."""


def flow_file_target_key(key: str, flow_id: str) -> str:
    """The key a stored file is written under where the flow is served.

    The file keeps its name and moves into the flow's own namespace. The serving side runs
    every flow as one service account, so a key namespaced to an editor user is refused by
    ``enforce_storage_key_scope``; the flow's id is a namespace that check always accepts,
    and flow ids are preserved across planes.

    This rule is permanent once a deployment has used it. Files on the serving side are
    physically stored under the keys it produces, so changing it orphans every file already
    copied. ``key`` must already be a storage key, as ``collect_flow_files`` reports one.
    """
    _, _, file_name = key.partition("/")
    return f"{validate_namespace(flow_id)}/{file_name}"


def rewrite_flow_file_keys_in_place(flow_data: dict | None, flow_id: str) -> dict[str, str]:
    """Point every storage key a flow's file inputs read at the flow's own namespace.

    Mutates ``flow_data``, so pass a copy: this is for the package a deploy sends, and the
    flow as stored keeps its original keys. Rewrites exactly the slot ``collect_flow_files``
    reads, which is the one the graph reads, so the files a copy carries and the keys the
    package names cannot disagree. Absolute paths and bare names are left as they are.

    Returns ``{source key: target key}`` for every key rewritten, including one already in
    the flow's namespace, which maps to itself.

    Raises ``FileKeyCollisionError`` when two different files would land on one key, as
    ``<user>/report.pdf`` and ``<flow>/report.pdf`` in one flow would. Neither is suffixed
    nor allowed to overwrite the other: either would silently hand a component the wrong
    document, so the deploy refuses and names both.
    """
    mapping: dict[str, str] = {}
    claimed: dict[str, str] = {}

    def rewrite(value: object) -> object:
        if not isinstance(value, str) or _why_not_a_key(value) is not None:
            return value
        namespace, _, file_name = value.partition("/")
        source = f"{validate_namespace(namespace)}/{file_name}"
        target = flow_file_target_key(source, flow_id)
        holder = claimed.setdefault(target, source)
        if holder != source:
            msg = (
                f"'{holder}' and '{source}' would both be stored as '{target}' in the serving "
                "environment; rename one of them before deploying"
            )
            raise FileKeyCollisionError(msg)
        mapping[source] = target
        return target

    for _node_id, _field_name, field in _file_fields(flow_data):
        slot = "file_path" if field.get("file_path") else "value"
        held = field.get(slot)
        if isinstance(held, list):
            field[slot] = [rewrite(item) for item in held]
        elif isinstance(held, str) and held.strip():
            field[slot] = rewrite(held)
    return mapping


def _file_field_values(flow_data: dict | None):
    """Yield ``(node_id, field_name, value)`` for every file field in the flow and its children."""
    for node_id, field_name, field in _file_fields(flow_data):
        for value in _raw_values(field):
            yield node_id, field_name, value


def _file_fields(flow_data: dict | None):
    """Yield ``(node_id, field_name, field)`` for every file field in the flow and its children."""
    frames = [flow_data]
    while frames:
        data = frames.pop()
        if not isinstance(data, dict):
            continue
        nodes = data.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, dict):
                continue
            inner = node.get("data", {}).get("node") if isinstance(node.get("data"), dict) else None
            if not isinstance(inner, dict):
                continue
            node_id = node.get("id") if isinstance(node.get("id"), str) else ""
            template = inner.get("template")
            if isinstance(template, dict):
                for field_name, field in template.items():
                    if isinstance(field, dict) and _is_file_field(field):
                        yield node_id, field_name, field
            # A node can carry another flow's data: a group node, which lfx's ``ungroup_node``
            # expands into the parent graph at build time. Its components therefore run as the
            # deployed flow and read files of their own, so they count here.
            nested = inner.get("flow")
            if isinstance(nested, dict) and isinstance(nested.get("data"), dict):
                frames.append(nested["data"])


def _is_file_field(field: dict) -> bool:
    """Whether a template field holds file paths.

    Matches ``param_handler._is_file_field`` so the scan sees the same fields the graph
    resolves at run time; a field either side does not recognise is a file left behind.
    """
    return field.get("type") == "file" or field.get("_input_type") == "FileInput"


def _raw_values(field: dict) -> list[str]:
    """The strings a file field holds, whether it keeps one or a list.

    ``file_path`` wins over ``value`` because the graph reads it first and falls back to
    ``value`` only when it is empty.
    """
    held = field.get("file_path") or field.get("value")
    # A blank is an optional input nobody filled, not a reference that failed to resolve.
    if isinstance(held, str):
        return [held] if held.strip() else []
    if isinstance(held, list):
        return [item for item in held if isinstance(item, str) and item.strip()]
    return []


def _why_not_a_key(value: str) -> str | None:
    """Why this value is not a storage key, or ``None`` when it is one."""
    if not isinstance(value, str) or not value.strip():
        return "empty"
    if value.startswith(("/", "\\")) or _WINDOWS_DRIVE.match(value):
        return "an absolute path on the editor's own machine, which the serving environment cannot resolve"
    namespace, separator, file_name = value.partition("/")
    if not separator:
        return "a bare file name with no namespace, so it does not address anything in storage"
    if not file_name or "/" in file_name or "\\" in file_name or ".." in file_name:
        return "not a '<namespace>/<file name>' storage key"
    try:
        validate_namespace(namespace)
    except ValueError:
        return "its namespace is not a user or flow id, so it is not a key storage would accept"
    return None
