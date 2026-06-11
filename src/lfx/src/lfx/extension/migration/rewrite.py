"""Walk a saved-flow payload and rewrite legacy component references.

The deserializer in ``Graph.from_payload`` calls :func:`migrate_flow_payload`
before constructing the graph.  The rewrite is intentionally tolerant:

    * Unknown reference -> typed ``component-not-found-with-hint`` collected
      into the report; the node keeps its old type so a partially-broken
      flow still loads as much as it can.  The frontend renders missing
      nodes as red placeholders today, which is the right UX.
    * Ambiguous bare name -> typed ``component-name-ambiguous`` and the node
      is left as-is.  We will not silently load it into the wrong bundle.
    * Already-canonical reference -> left untouched (idempotent).
    * Unknown shape (non-dict node, missing 'data' field) -> skipped, no
      error.  The caller's own validation handles malformed payloads.

The rewriter mutates ``payload`` in place because the saved-flow object is
already a freshly-decoded dict tree owned by the caller; copying every node
just to swap one string per node is wasteful and would force callers to
re-bind their reference.  This is the one mutation in the migration system;
everything else is frozen Pydantic models.

The function returns a :class:`MigrationReport` with one record per node it
visited so the caller (today: nothing; tomorrow: ``ExtensionEventsService``)
can emit one ``flow-migrated`` event per flow per session.
"""

from __future__ import annotations

import difflib
import sys
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

from lfx.extension.errors import ExtensionError
from lfx.extension.migration.loader import load_migration_table
from lfx.extension.migration.schema import (
    _NAMESPACED_ID_RE,
    MigrationEntry,
    MigrationTable,
)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

RewriteOutcome = Literal["rewritten", "already_canonical", "known_current_component", "unmapped", "ambiguous"]


@dataclass(frozen=True)
class NodeRewriteRecord:
    """One node visited by the rewriter.

    Frozen because reports are passed through events / log lines and we do
    not want callers patching them mid-flight.
    """

    node_id: str
    legacy_value: str
    new_value: str | None
    legacy_form_kind: str | None
    outcome: RewriteOutcome
    error: ExtensionError | None = None


@dataclass
class MigrationReport:
    """Summary of a single migration pass.

    ``rewritten`` counts only successful rewrites; ``already_canonical``
    nodes are not migrations and do not trigger a ``flow-migrated`` event.
    ``records`` retains every visited node (including no-ops) for debugging
    and the future events emitter.
    """

    records: list[NodeRewriteRecord] = field(default_factory=list)
    errors: list[ExtensionError] = field(default_factory=list)

    @property
    def rewritten_count(self) -> int:
        return sum(1 for r in self.records if r.outcome == "rewritten")

    @property
    def any_rewritten(self) -> bool:
        return self.rewritten_count > 0


# ---------------------------------------------------------------------------
# Reference probing
# ---------------------------------------------------------------------------


def _is_canonical(value: str) -> bool:
    """Return True if ``value`` is already in ``ext:<bundle>:<Class>@<slot>`` shape."""
    return bool(_NAMESPACED_ID_RE.fullmatch(value))


def _resolve_legacy_reference(
    value: str,
    table: MigrationTable,
) -> tuple[MigrationEntry | None, list[MigrationEntry]]:
    """Look ``value`` up in the table.

    Returns a ``(winner, candidates)`` pair:

        * ``winner`` is the single entry that maps ``value`` if exactly one
          entry matches, else ``None``.
        * ``candidates`` is the list of every entry that matched -- length 0
          means unmapped, length 1 means the unique match (== ``winner``),
          length >= 2 means ambiguous (only possible for pathological tables
          where the schema-level unique check has been bypassed; we still
          guard at runtime so a hand-edited deployment table cannot silently
          load into the wrong bundle).

    Probe order is bare_class_name -> import_path -> legacy_slot.  In a
    well-formed table only one bucket matches per ``value``.
    """
    candidates: list[MigrationEntry] = []
    bare = table.lookup_bare(value)
    if bare is not None:
        candidates.append(bare)
    imp = table.lookup_import_path(value)
    if imp is not None:
        candidates.append(imp)
    legacy = table.lookup_legacy_slot(value)
    if legacy is not None:
        candidates.append(legacy)

    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


# Beyond this node count we skip the ``difflib`` "did you mean" suggestion
# pass.  ``get_close_matches`` is O(nodes * table * len(name)^2) and runs on
# the flow-load request path; an adversarial payload with thousands of
# unmapped nodes could otherwise pin a worker.  Above the threshold the
# rewriter still does the table lookup and surfaces the typed error -- the
# only thing dropped is the suggestion list in the hint.
_SUGGESTION_NODE_THRESHOLD: int = 200


def _closest_matches(value: str, known: list[str], *, n: int = 3) -> list[str]:
    """Return up to ``n`` strings from ``known`` that are closest to ``value``.

    Wraps :func:`difflib.get_close_matches` so the suggestion logic lives in
    one place.  Cutoff is intentionally permissive (0.6) so we surface a
    suggestion even when the user's typo is several edits off; an empty
    list means the rewriter prints a generic 'no close match' hint.
    """
    if not known:
        return []
    return difflib.get_close_matches(value, known, n=n, cutoff=0.6)


# ---------------------------------------------------------------------------
# Current component detection
# ---------------------------------------------------------------------------


def _component_type_aliases(components: Mapping[str, Any]) -> set[str]:
    """Return component names plus locally-derived aliases for a category."""
    from lfx.utils.component_aliases import get_component_type_aliases

    known: set[str] = set()
    for component_name, component_data in components.items():
        if not isinstance(component_name, str) or not component_name:
            continue
        metadata = component_data if isinstance(component_data, Mapping) else None
        known.update(get_component_type_aliases(component_name, metadata))
    return known


@lru_cache(maxsize=1)
def _known_current_types_from_index() -> frozenset[str]:
    """Return current component type names from the bundled component index.

    This intentionally reads the local index without building component
    templates or mutating the runtime component cache.
    """
    try:
        from lfx.graph.flow_builder.builder import load_local_registry

        registry = load_local_registry()
    except Exception:  # noqa: BLE001
        return frozenset()

    return frozenset(_component_type_aliases(registry))


def _known_current_types_from_cache() -> set[str]:
    """Return aliases from the live component cache if it is already loaded."""
    components_module = sys.modules.get("lfx.interface.components")
    if components_module is None:
        return set()

    component_cache = getattr(components_module, "component_cache", None)
    all_types_dict = getattr(component_cache, "all_types_dict", None)
    if not isinstance(all_types_dict, Mapping):
        return set()

    known: set[str] = set()
    components = all_types_dict.get("components")
    categories = components if isinstance(components, Mapping) else all_types_dict
    for category_components in categories.values():
        if isinstance(category_components, Mapping):
            known.update(_component_type_aliases(category_components))
    return known


def _known_current_types() -> frozenset[str]:
    """Return component type names that are current, not migration misses."""
    return frozenset(_known_current_types_from_index() | _known_current_types_from_cache())


# ---------------------------------------------------------------------------
# Node-level rewrite
# ---------------------------------------------------------------------------

# Saved-flow node shape (current Langflow): the canonical legacy reference
# lives at ``node["data"]["type"]`` and is the bare class name (e.g.
# ``"OpenAIEmbeddings"``).  Older serializations also stored an
# ``import_path`` at ``node["data"]["node"]["template"]["code"]["value"]``-
# adjacent locations; we only rewrite the ``data.type`` field here because
# that is the field the runtime resolves nodes by.  Other legacy fields are
# decorative and the post-rewrite ``data.type`` is enough for the loader.

_TYPE_FIELD_PATH: tuple[str, ...] = ("data", "type")


def _read_type(node: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    """Return ``(value, container)`` where ``container[<last>]`` holds it.

    ``None, None`` if the path doesn't exist or the leaf isn't a string.
    """
    cursor: Any = node
    container: dict[str, Any] | None = None
    last_key: str | None = None
    for key in _TYPE_FIELD_PATH:
        if not isinstance(cursor, dict):
            return None, None
        container = cursor
        last_key = key
        cursor = cursor.get(key)
    if not isinstance(cursor, str):
        return None, None
    if last_key is None or container is None:
        return None, None
    # Sanity: container is dict, last_key is str, cursor is the existing
    # value at that key.  We return container so the caller can write back.
    return cursor, container


def _rewrite_one_node(
    node: dict[str, Any],
    *,
    table: MigrationTable,
    known_legacy: list[str],
    known_current_types: Collection[str],
    node_index: int,
) -> NodeRewriteRecord | None:
    """Rewrite ``node["data"]["type"]`` if needed.

    Returns the per-node record, or ``None`` for nodes whose shape we don't
    recognize (note nodes, malformed payloads, etc.).  ``None`` records do
    not appear in the report.
    """
    if not isinstance(node, dict):
        return None
    react_flow_type = node.get("type")
    if isinstance(react_flow_type, str) and react_flow_type != "genericNode":
        return None

    legacy_value, container = _read_type(node)
    if legacy_value is None or container is None:
        return None

    node_id = ""
    if isinstance(node.get("id"), str):
        node_id = node["id"]
    elif isinstance(node.get("data"), dict) and isinstance(node["data"].get("id"), str):
        node_id = node["data"]["id"]
    else:
        node_id = f"<unindexed-{node_index}>"

    if _is_canonical(legacy_value):
        return NodeRewriteRecord(
            node_id=node_id,
            legacy_value=legacy_value,
            new_value=legacy_value,
            legacy_form_kind=None,
            outcome="already_canonical",
        )

    winner, candidates = _resolve_legacy_reference(legacy_value, table)

    # Two or more candidates means the legacy value matched in multiple
    # buckets (bare/import_path/legacy_slot) -- always ambiguous.
    if len(candidates) > 1:
        # Ambiguous bare-name (or, pathologically, multi-bucket match).
        # Surface a typed error and DO NOT rewrite.  ``content-name-ambiguous``
        # tells the operator exactly which targets collide so they can
        # rename the offending bundle's class or remove the bare-name entry.
        target_list = ", ".join(sorted(c.target for c in candidates))
        err = ExtensionError(
            code="component-name-ambiguous",
            message=(f"Legacy reference {legacy_value!r} matches more than one migration entry: {target_list}."),
            location=node_id,
            content=legacy_value,
            hint=(
                "Open the flow JSON and replace the bare class name with the "
                "canonical 'ext:<bundle>:<Class>@official' form for the bundle "
                "you actually want, then re-save."
            ),
        )
        return NodeRewriteRecord(
            node_id=node_id,
            legacy_value=legacy_value,
            new_value=None,
            legacy_form_kind=None,
            outcome="ambiguous",
            error=err,
        )

    if winner is None:
        # Before falling through to ``component-not-found-with-hint``, check
        # the ambiguous-bare-names list.  A bare class name that exists in
        # 2+ bundles cannot have a regular auto-rewrite entry (the CI guard
        # rejects it), so its only surface is the explicit ambiguity
        # marker.  Surfacing ``component-name-ambiguous`` here -- with
        # the candidate targets enumerated -- is the migration contract:
        # we will not silently load an ambiguous name into the wrong
        # bundle, and we tell the operator exactly which targets they
        # have to choose between.
        ambig_marker = table.lookup_ambiguous_bare(legacy_value)
        if ambig_marker is not None:
            target_list = ", ".join(ambig_marker.candidates)
            err = ExtensionError(
                code="component-name-ambiguous",
                message=(f"Bare class name {legacy_value!r} exists in multiple bundles: {target_list}."),
                location=node_id,
                content=legacy_value,
                hint=(
                    "Open the flow JSON and replace the type field with the "
                    "specific canonical 'ext:<bundle>:<Class>@official' ID "
                    "for the bundle you actually want."
                ),
            )
            return NodeRewriteRecord(
                node_id=node_id,
                legacy_value=legacy_value,
                new_value=None,
                legacy_form_kind=None,
                outcome="ambiguous",
                error=err,
            )

        if legacy_value in known_current_types:
            return NodeRewriteRecord(
                node_id=node_id,
                legacy_value=legacy_value,
                new_value=legacy_value,
                legacy_form_kind=None,
                outcome="known_current_component",
            )

        suggestions = _closest_matches(legacy_value, known_legacy)
        if suggestions:
            hint = (
                "Did you mean one of: "
                + ", ".join(repr(s) for s in suggestions)
                + "?  Open the flow JSON and replace the type field "
                "with the matching canonical 'ext:<bundle>:<Class>@official' ID."
            )
        else:
            hint = (
                "No close match found in the migration table.  This component "
                "may have been removed; replace the node or restore the "
                "original distribution."
            )
        err = ExtensionError(
            code="component-not-found-with-hint",
            message=f"Legacy reference {legacy_value!r} is not in the migration table.",
            location=node_id,
            content=legacy_value,
            hint=hint,
        )
        return NodeRewriteRecord(
            node_id=node_id,
            legacy_value=legacy_value,
            new_value=None,
            legacy_form_kind=None,
            outcome="unmapped",
            error=err,
        )

    # Successful rewrite.  Mutate the node in place at data.type so the
    # downstream graph builder sees the canonical form.
    container[_TYPE_FIELD_PATH[-1]] = winner.target
    return NodeRewriteRecord(
        node_id=node_id,
        legacy_value=legacy_value,
        new_value=winner.target,
        legacy_form_kind=winner.legacy_form_kind,
        outcome="rewritten",
    )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def migrate_flow_payload(
    payload: dict[str, Any],
    *,
    table: MigrationTable | None = None,
    known_current_types: Collection[str] | None = None,
) -> MigrationReport:
    """Rewrite legacy component references in ``payload`` in place.

    Args:
        payload: The flow payload as produced by JSON deserialization
            (``{"data": {"nodes": [...], "edges": [...]}}`` or just
            ``{"nodes": [...], "edges": [...]}``).  Mutated in place.
        table: A pre-loaded migration table.  ``None`` means call
            :func:`load_migration_table` and use the result; if loading
            fails, the deserializer falls back to an empty table so every
            legacy reference becomes unmapped (with hint) instead of the
            entire flow load crashing.
        known_current_types: Current component type names and aliases that
            should be left unchanged without emitting migration errors.
            ``None`` means derive them from the bundled index and any already
            populated component cache.

    Returns:
        A :class:`MigrationReport` summarizing every node that was visited
        and any errors that were emitted.

    Raises:
        TypeError: ``payload`` is not a dict.  Programmer-error path; saved
            flows always deserialize into a dict.
    """
    if not isinstance(payload, dict):
        msg = f"migrate_flow_payload requires a dict payload (got {type(payload).__name__})"
        raise TypeError(msg)

    report = MigrationReport()

    if table is None:
        loaded_table, load_error = load_migration_table()
        if load_error is not None or loaded_table is None:
            # Surface the load error on the report so the caller can decide
            # whether to fail the flow load (currently no caller does; the
            # deserializer tolerates this so a corrupt table doesn't take
            # the whole server down).  Subsequent rewrites then run with
            # an empty in-memory table.
            if load_error is not None:
                report.errors.append(load_error)
            from lfx.extension.migration.loader import empty_table

            table = empty_table()
        else:
            table = loaded_table

    # Saved-flow files ship as ``{"data": {"nodes": [...], "edges": [...]}}``
    # but ``Graph.from_payload`` accepts either.  Mirror that here.
    inner = payload["data"] if "data" in payload and isinstance(payload["data"], dict) else payload
    nodes = inner.get("nodes")
    if not isinstance(nodes, list):
        return report

    # Cap difflib suggestion cost: for very large flows the per-unmapped-node
    # ``get_close_matches`` pass dominates flow-load latency.  Above the
    # threshold we still do the table lookup (the migration runs) but skip
    # the suggestion list in the typed error's hint -- the user-facing
    # signal (the rewrite itself or the typed error) is unaffected.
    suggestion_pool: list[str] = table.all_known_legacy_values() if len(nodes) <= _SUGGESTION_NODE_THRESHOLD else []
    current_types = known_current_types if known_current_types is not None else _known_current_types()
    for index, node in enumerate(nodes):
        record = _rewrite_one_node(
            node,
            table=table,
            known_legacy=suggestion_pool,
            known_current_types=current_types,
            node_index=index,
        )
        if record is None:
            continue
        report.records.append(record)
        if record.error is not None:
            report.errors.append(record.error)

    # flow_migrated and extension_error events are emitted by the caller
    # (Graph.from_payload in base.py) which has the flow_id in scope.
    # See LE-1017.
    return report
