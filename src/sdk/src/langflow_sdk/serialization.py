"""Git-friendly flow serialization for langflow-sdk.

``normalize_flow`` transforms a raw Langflow flow dict into a stable,
diff-friendly representation suitable for committing to version control:

- **Volatile fields stripped** -- ``updated_at``, ``user_id``, ``folder_id``,
  and ``created_at`` are removed so unrelated server-side changes don't
  produce noise in diffs.
- **Secrets cleared** -- template fields marked ``password=True`` or
  ``load_from_db=True`` have their ``value`` set to ``""`` so credentials are
  never committed.
- **Keys sorted recursively** -- every dict at every depth is sorted so that
  identical flows always produce byte-for-byte identical JSON regardless of the
  order the server returned keys.
- **Code as lines** *(opt-in)* -- template fields whose ``type`` is ``"code"``
  have their ``value`` converted from a single string to a list of lines,
  making per-line diffs readable in pull requests.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# Top-level flow keys that carry instance-specific state and should not be
# version-controlled.
_VOLATILE_TOP_LEVEL: frozenset[str] = frozenset(
    {
        "updated_at",
        "created_at",
        "user_id",
        "folder_id",
        "access_type",
        "gradient",
    }
)

# Node-position keys that change every time a node is dragged; stripping them
# keeps diffs focused on logic rather than layout.  Off by default because
# layout is sometimes intentional.
_VOLATILE_NODE_KEYS: frozenset[str] = frozenset(
    {
        "positionAbsolute",
        "dragging",
        "selected",
    }
)


def _sort_recursive(obj: Any) -> Any:
    """Recursively sort all dict keys; leave other types untouched."""
    if isinstance(obj, dict):
        return {k: _sort_recursive(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_recursive(item) for item in obj]
    return obj


def _strip_node_volatile(node: dict[str, Any]) -> dict[str, Any]:
    """Remove transient display keys from a node dict."""
    return {k: v for k, v in node.items() if k not in _VOLATILE_NODE_KEYS}


def _process_template_field(
    field: dict[str, Any],
    *,
    strip_secrets: bool,
    code_as_lines: bool,
) -> dict[str, Any]:
    """Return a (possibly mutated copy of) a single template field dict."""
    field = dict(field)

    if strip_secrets and (field.get("password") or field.get("load_from_db")):
        field["value"] = ""

    if code_as_lines and field.get("type") == "code":
        value = field.get("value")
        if isinstance(value, str):
            field["value"] = value.split("\n")
        elif isinstance(value, list):
            pass  # already lines -- leave as-is

    return field


def _process_node(
    node: dict[str, Any],
    *,
    strip_secrets: bool,
    code_as_lines: bool,
    strip_node_volatile: bool,
) -> dict[str, Any]:
    """Return a processed copy of a single node."""
    node = dict(node)

    if strip_node_volatile:
        node = _strip_node_volatile(node)

    node_data: dict[str, Any] = dict(node.get("data") or {})
    node_inner: dict[str, Any] = dict(node_data.get("node") or {})
    template: dict[str, Any] = dict(node_inner.get("template") or {})

    processed_template: dict[str, Any] = {}
    for field_name, field_def in template.items():
        if isinstance(field_def, dict):
            processed_template[field_name] = _process_template_field(
                field_def,
                strip_secrets=strip_secrets,
                code_as_lines=code_as_lines,
            )
        else:
            processed_template[field_name] = field_def

    node_inner["template"] = processed_template
    node_data["node"] = node_inner
    node["data"] = node_data
    return node


def normalize_flow(
    flow: dict[str, Any],
    *,
    strip_volatile: bool = True,
    strip_secrets: bool = True,
    sort_keys: bool = True,
    code_as_lines: bool = False,
    strip_node_volatile: bool = True,
) -> dict[str, Any]:
    """Return a git-friendly copy of *flow*.

    Parameters
    ----------
    flow:
        Raw flow dict as returned by the Langflow API or read from a ``.json``
        file.
    strip_volatile:
        Remove top-level fields that carry instance-specific state
        (``updated_at``, ``user_id``, ``folder_id``, ``created_at``).
    strip_secrets:
        Clear ``value`` on template fields marked ``password=True`` or
        ``load_from_db=True``.
    sort_keys:
        Recursively sort all dict keys so the output is deterministic.
    code_as_lines:
        Convert ``type="code"`` template field values from a single string
        to a list of lines for cleaner per-line diffs.
    strip_node_volatile:
        Remove ``positionAbsolute``, ``dragging``, and ``selected`` keys from
        individual nodes (they change whenever a node is dragged in the UI).

    Returns:
    -------
    dict[str, Any]
        A new dict -- the original is never mutated.
    """
    result: dict[str, Any] = copy.deepcopy(flow)

    if strip_volatile:
        for key in _VOLATILE_TOP_LEVEL:
            result.pop(key, None)

    data: dict[str, Any] = dict(result.get("data") or {})
    nodes: list[Any] = list(data.get("nodes") or [])

    processed_nodes = [
        _process_node(
            n,
            strip_secrets=strip_secrets,
            code_as_lines=code_as_lines,
            strip_node_volatile=strip_node_volatile,
        )
        if isinstance(n, dict)
        else n
        for n in nodes
    ]
    data["nodes"] = processed_nodes
    result["data"] = data

    if sort_keys:
        result = _sort_recursive(result)

    return result


def normalize_flow_file(
    path: Path,
    *,
    strip_volatile: bool = True,
    strip_secrets: bool = True,
    sort_keys: bool = True,
    code_as_lines: bool = False,
    strip_node_volatile: bool = True,
) -> dict[str, Any]:
    """Read *path*, normalize it, and return the result dict.

    Raises:
    ------
    FileNotFoundError
        If *path* does not exist.
    json.JSONDecodeError
        If the file is not valid JSON.
    """
    raw = Path(path).read_text(encoding="utf-8")
    flow = json.loads(raw)
    return normalize_flow(
        flow,
        strip_volatile=strip_volatile,
        strip_secrets=strip_secrets,
        sort_keys=sort_keys,
        code_as_lines=code_as_lines,
        strip_node_volatile=strip_node_volatile,
    )


def flow_to_json(flow: dict[str, Any], *, indent: int = 2) -> str:
    """Serialize *flow* to a deterministic JSON string.

    Keys are **not** sorted here because ``normalize_flow`` with
    ``sort_keys=True`` (the default) already does that; this function just
    handles the final encoding.
    """
    return json.dumps(flow, indent=indent, ensure_ascii=False) + "\n"
