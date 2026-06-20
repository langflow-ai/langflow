"""Convert a legacy xyflow diagram graph (``diagram_json``) into D2 source (D.13).

Epic D pivoted the diagram artifact from an xyflow graph to D2 source.  Projects
created before the D.2 landing have ``diagram_json`` populated but ``diagram_d2``
NULL.  This module is the pure conversion step that bridges that gap — no DB, no
LLM, no async.  It is called by the D.13 Alembic data migration, which visits
every such row once and writes the produced D2 into ``diagram_d2``.

Why convert rather than dual-read?
-----------------------------------
Dual-read would require keeping the xyflow render path alive in the frontend
forever — but that path is being deleted in D.15 (xyflow removal).  There is no
viable fallback once the canvas no longer knows how to render an xyflow graph.
Converting the stored data now means every project, old or new, is served by the
single D2 path that D.6 already supports.  The original ``diagram_json`` column
is left untouched (no data loss); dropping it is a later, separate migration.

Output format
-------------
The produced D2 matches the shape the generation engine (``diagram_generation.py``)
emits and that the rest of the system (D.3 gate, D.6 render, D.7 anchors, D.8
refinement) already understands::

    shape: sequence_diagram
    user: User
    api: API

    user -> api: submit form
    api -> user: 200 OK

Rules applied (mirrors ``diagram_generation.SYSTEM_PROMPT``):

- ``shape: sequence_diagram`` header.
- Participant block: one ``id: Label`` line per node, in their original list order.
- Message block: one connection line per edge, sorted ascending by ``data.order``;
  an edge missing ``data.order`` (or carrying a non-int one) sorts *after* every
  ordered edge, so a partially-ordered legacy graph keeps its sequence.
- ``->`` for synchronous messages; ``-->`` when ``animated: true`` OR
  ``data.kind`` is ``"async"`` or ``"return"`` (dashed in the original canvas).
- Edge label comes from ``edge.data.label``; if absent the colon remains, yielding
  ``source -> target:`` which D2 accepts (empty label, no visual noise).

Legacy ids were free-form, but several characters are *structural* in D2 — a dot
nests one container inside another (``svc.api`` would become ``api`` inside
``svc``), and whitespace / ``->`` / ``:`` delimit tokens.  So each node id is
slugified to a safe token and edge endpoints are remapped through the same map;
labels have their whitespace (including newlines, which would otherwise split a
statement) collapsed to single spaces.  Anything the converter can't make sense
of is dropped rather than emitted as broken D2, and the D.13 migration additionally
compile-checks the result and skips (leaves ``diagram_d2`` NULL) on failure — so a
bad legacy row degrades to "regenerate", never a broken stored diagram.

This module intentionally does NOT import from ``diagram.py`` (that module is
scheduled for deletion in D.15).  The xyflow graph shape is parsed from raw dicts
instead — the structure is simple enough that Pydantic models are not needed for a
one-shot migration path.
"""

from __future__ import annotations

import json
import re

# Anything outside this set is structural or unsafe in a D2 id; runs of it become
# a single hyphen so a legacy id like "svc.api" or "Order Service" maps to one
# flat, safe participant token rather than a nested container or a parse error.
_UNSAFE_ID_CHARS = re.compile(r"[^a-z0-9_-]+")


def _slug(raw: object, fallback: str) -> str:
    """Slugify a free-form id to a safe lowercase D2 token, or `fallback` if empty."""
    slug = _UNSAFE_ID_CHARS.sub("-", str(raw).strip().lower()).strip("-")
    return slug or fallback


def _clean_label(raw: object, fallback: str) -> str:
    """Collapse a label's whitespace (incl. newlines) to single spaces; `fallback` if blank.

    D2 reads a label to end-of-line, so an embedded newline would split one
    statement into two — collapsing whitespace keeps the label on its own line.
    """
    if raw is None:
        return fallback
    text = " ".join(str(raw).split())
    return text or fallback


def _is_dashed(edge: dict) -> bool:
    """Return True if the edge should render as a dashed/return arrow (``-->``).

    Three sources of "dashed" in the xyflow graph:
    - ``edge.animated`` is truthy (the xyflow canvas rendered it animated/dashed).
    - ``edge.data.kind == "async"`` (labelled asynchronous call).
    - ``edge.data.kind == "return"`` (labelled return/response arrow).
    """
    if edge.get("animated"):
        return True
    kind = (edge.get("data") or {}).get("kind") or ""
    return kind in ("async", "return")


def _order_key(edge: dict) -> tuple[int, int]:
    """Sort key: ordered edges first (ascending by order), then unordered edges.

    `(0, order)` for an edge with an integer ``data.order`` (bool excluded, since
    `True == 1`), `(1, 0)` otherwise — so a missing or non-int order sorts strictly
    *after* every explicitly-ordered edge, and a legitimate ``order: 0`` stays
    first. Python's sort is stable, so unordered edges keep their relative order.
    """
    value = (edge.get("data") or {}).get("order")
    if isinstance(value, int) and not isinstance(value, bool):
        return (0, value)
    return (1, 0)


def xyflow_graph_to_d2(graph: dict | str) -> str:
    """Convert an xyflow diagram graph to D2 sequence-diagram source.

    Accepts the value stored in ``lothal_project.diagram_json`` — either the raw
    JSON string or an already-parsed dict.  Returns a D2 source string that:

    - starts with ``shape: sequence_diagram``,
    - declares each participant once as ``id: Label`` in their original node-list
      order (ids slugified to safe D2 tokens),
    - emits one connection line per edge, sorted by ``edge.data.order`` ascending
      (unordered edges last), using ``->`` for synchronous and ``-->`` for
      asynchronous/return arrows.

    Tolerates missing/extra keys gracefully: a node without a label falls back to
    its id; an edge without a label yields a bare ``source -> target:``; an edge
    missing both endpoints is dropped. Raises ``ValueError`` when the input is not
    a JSON object or has no nodes — a zero-node graph cannot be a sequence diagram
    and should be skipped by the migration.
    """
    if isinstance(graph, str):
        try:
            graph = json.loads(graph)
        except json.JSONDecodeError as exc:
            msg = f"diagram_json is not valid JSON: {exc}"
            raise ValueError(msg) from exc

    if not isinstance(graph, dict):
        # ValueError (not TypeError) is the deliberate contract: the migration's
        # per-row skip and the converter's no-nodes case both raise ValueError, so
        # a malformed stored value is one catch, not two.
        msg = f"diagram_json must be a JSON object, got {type(graph).__name__}."
        raise ValueError(msg)  # noqa: TRY004

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    nodes = nodes if isinstance(nodes, list) else []
    edges = [e for e in edges if isinstance(e, dict)] if isinstance(edges, list) else []

    if not nodes:
        msg = "Cannot convert an xyflow graph with no nodes to D2."
        raise ValueError(msg)

    lines: list[str] = ["shape: sequence_diagram"]

    # Declare participants in original node order (left-to-right reading order on
    # the old canvas). Map each original id → its safe slug so edge endpoints
    # below resolve to the same token; keep slugs unique within the diagram.
    id_map: dict[str, str] = {}
    used: set[str] = set()
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        raw_id = node.get("id")
        slug = _slug(raw_id, f"n{i}")
        unique = slug
        suffix = 2
        while unique in used:
            unique = f"{slug}-{suffix}"
            suffix += 1
        used.add(unique)
        if raw_id is not None:
            id_map[str(raw_id)] = unique
        lines.append(f"{unique}: {_clean_label((node.get('data') or {}).get('label'), unique)}")

    # Blank line separates declarations from messages (matches the generation engine).
    lines.append("")

    for edge in sorted(edges, key=_order_key):
        src_raw = edge.get("source")
        tgt_raw = edge.get("target")
        if not src_raw or not tgt_raw:
            continue  # a connection needs both endpoints
        source = id_map.get(str(src_raw)) or _slug(src_raw, "n")
        target = id_map.get(str(tgt_raw)) or _slug(tgt_raw, "n")
        label = _clean_label((edge.get("data") or {}).get("label"), "")
        arrow = "-->" if _is_dashed(edge) else "->"
        lines.append(f"{source} {arrow} {target}: {label}")

    return "\n".join(lines)
