from itertools import product
from random import Random
from uuid import UUID

from langflow.services.tracing import span_sorting


def scan_order(items):
    """Reference the original left-to-right scan, including orphan and cycle handling."""
    ids = {span_id for _, span_id, _ in items}
    remaining = [(data, span_id, parent if parent in ids else None) for data, span_id, parent in items]
    missing = sum(parent is not None and parent not in ids for _, _, parent in items)
    warnings = []
    if missing:
        warnings.append(("Detached %d tracing spans from missing parents to preserve database integrity.", missing))
    ordered = []
    inserted = set()
    while remaining:
        blocked = []
        for item in remaining:
            _, span_id, parent = item
            if parent is None or parent in inserted:
                ordered.append(item)
                inserted.add(span_id)
            else:
                blocked.append(item)
        if len(blocked) == len(remaining):
            warnings.append(
                (
                    "Detected cycle or unresolvable span dependencies in tracing batch; "
                    "breaking parent relationships for %d spans to preserve DB integrity.",
                    len(blocked),
                )
            )
            ordered.extend((data, span_id, None) for data, span_id, _ in blocked)
            break
        remaining = blocked
    return ordered, warnings


def test_span_order_matches_scan(monkeypatch):
    warnings = []
    monkeypatch.setattr(span_sorting.logger, "warning", lambda *args: warnings.append(args))

    def check(graph):
        items = [({"position": i, "parent_span_id": p}, span_id, p) for i, (span_id, p) in enumerate(graph)]
        original = [(data.copy(), span_id, parent) for data, span_id, parent in items]
        expected, expected_warnings = scan_order(items)
        warnings.clear()
        actual = span_sorting.topological_sort_spans(items)
        assert actual == expected
        assert warnings == expected_warnings
        assert items == original
        assert all(item[0] is ref[0] for item, ref in zip(actual, expected, strict=True))

    ids = [UUID(int=i) for i in range(10)]
    edges = list(product(ids[:2], [None, *ids[:3]]))
    for size in range(4):
        for graph in product(edges, repeat=size):
            check(graph)

    rng = Random(16262)  # noqa: S311 - reproduce the same graph fixtures across runs
    for _ in range(100):
        check([(rng.choice(ids[:-1]), rng.choice([None, *ids])) for _ in range(30)])
