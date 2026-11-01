"""``GraphPlain``: a flow graph read once, to run many checks on it.

A save validates the graph it receives, may repair it, compares it with the
stored graph, diffs the two, and hashes the result. Each of those calls on
its own reads its graphs again. A plain graph is read once and kept as it
is, with no index and no check, so each call costs only its own work.

A plain graph remembers which checks it has passed, and a later call that
needs the same check skips it. The graph cannot change, so a check that
passed once stays passed. This is the Rust engine's ``lfx::ops::plain``.
"""

from __future__ import annotations

from typing import Any

from lfx.services.flow_operations.canonical import graph_hash_checked, graphs_equal
from lfx.services.flow_operations.diff import derive_checked
from lfx.services.flow_operations.repair import GraphFix, repair_checked
from lfx.services.flow_operations.validation import GraphViolation, find_graph_violations, validate_flow_data


class GraphPlain:
    """A flow graph that no rule has been checked on yet. It shares its value, which nothing changes."""

    __slots__ = ("_clean_against", "_flow", "_full", "_structure", "_violations_against")

    def __init__(self, flow: Any, *, checked: bool = False) -> None:
        self._flow = flow
        # The graph has no structural violation.
        self._structure = checked
        # The graph has no violation at all, numbers that are not finite included.
        self._full = checked
        # A base the graph has no violation against, with every check.
        self._clean_against: GraphPlain | None = None
        # The last base the graph was checked against with every check, and its violations, for repair.
        self._violations_against: tuple[GraphPlain | None, list[GraphViolation]] | None = None

    @property
    def value(self) -> Any:
        """The graph. The caller must not change it."""
        return self._flow

    def _passed(self, *, check_values: bool) -> bool:
        return self._full if check_values else self._structure

    def _pass(self, *, check_values: bool) -> None:
        self._structure = True
        if check_values:
            self._full = True

    def require(self, *, check_values: bool, context: str) -> None:
        """Raise with the graph's violations, unless the check passed before."""
        if not self._passed(check_values=check_values):
            validate_flow_data(self._flow, check_values=check_values, context=context)
            self._pass(check_values=check_values)

    def violations(self, base: GraphPlain | None = None, *, check_values: bool = True) -> list[GraphViolation]:
        """Every rule the graph breaks, against the stored graph a write replaces when given."""
        if base is None and self._passed(check_values=check_values):
            return []
        violations = find_graph_violations(
            self._flow, check_values=check_values, base=None if base is None else base.value
        )
        if check_values:
            self._violations_against = (base, violations)
        # The rules against a base include the rules of the graph alone.
        if not violations:
            self._pass(check_values=check_values)
            if base is not None and check_values:
                self._clean_against = base
        return violations

    def repair(self, base: GraphPlain | None = None) -> tuple[GraphPlain, list[GraphFix]]:
        """A copy with every violation that has one fix fixed, and the fixes.

        A graph that breaks no rule against ``base`` comes back as it is: repair
        would change nothing in it, and a plain graph never changes.
        """
        clean = self._full if base is None else self._clean_against is base
        if clean:
            return GraphPlain(self._flow, checked=True), []
        known = self._violations_against
        violations = known[1] if known is not None and known[0] is base else None
        repaired = repair_checked(self._flow, base=None if base is None else base.value, violations=violations)
        # Repair checks every rule on what it returns.
        return GraphPlain(repaired.flow_data, checked=True), repaired.fixes

    def graph_hash(self) -> str:
        """The SHA-256 hex digest of the graph's canonical form."""
        return graph_hash_checked(self._flow)

    def equals(self, other: GraphPlain) -> bool:
        """Whether two graphs are the same graph."""
        return graphs_equal(self._flow, other.value)

    def ops_diff(self, target: GraphPlain) -> list[dict[str, Any]]:
        """The operations that turn this graph into ``target``, checked by replay. They share ``target``'s values."""
        self.require(check_values=False, context="flow.data")
        target.require(check_values=True, context="target flow.data")
        operations, _flow_data = derive_checked(self._flow, target.value)
        return operations
