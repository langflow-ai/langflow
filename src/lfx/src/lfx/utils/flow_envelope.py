"""Outer-envelope handling for flow JSON — the single source of truth.

Exported Langflow flows wrap the graph in an envelope::

    {"name": ..., "description": ..., "data": {"nodes": [...], "edges": [...]}}

The inner graph is ``{"nodes": [...], "edges": [...]}``. The graph loader
(``aload_flow_from_json``) needs the ``{"data": ...}`` envelope, while the upgrade
checker/applier operate on the inner graph. Detecting, unwrapping, and re-wrapping
that envelope used to be hand-rolled (``raw.get("data", raw)``) in several call sites
with subtly different rules; these helpers consolidate it so the paths can't diverge.
"""

from __future__ import annotations


def split_flow_envelope(payload: dict) -> tuple[dict | None, dict]:
    """Split a parsed flow payload into ``(outer_envelope_or_None, inner_graph)``.

    A payload is treated as enveloped when its ``"data"`` value is itself a dict (the
    exported-flow shape); otherwise it is already a bare graph and is returned unchanged
    as the inner graph (with ``None`` for the envelope).

    Raises:
        TypeError: if ``payload`` is not a dict — a flow must be a JSON object, so a
            top-level array/string/number is rejected loudly instead of crashing later
            with an opaque ``AttributeError``.
    """
    if not isinstance(payload, dict):
        msg = f"flow JSON must be a JSON object, got {type(payload).__name__}"
        raise TypeError(msg)
    data = payload.get("data")
    if isinstance(data, dict):
        return payload, data
    return None, payload


def merge_flow_envelope(outer: dict | None, inner: dict, *, wrap_bare: bool) -> dict:
    """Recombine an inner graph with its outer envelope.

    - Enveloped source (``outer`` is not None): returns ``{**outer, "data": inner}``,
      preserving outer metadata (``name``/``description``/...) while swapping in the
      (possibly upgraded) inner graph.
    - Bare source (``outer`` is None): returns ``{"data": inner}`` when ``wrap_bare`` is
      True (for the graph loader, which requires the envelope) or the bare ``inner``
      unchanged when False (for ``lfx upgrade --write``, which preserves the on-disk shape).
    """
    if outer is not None:
        return {**outer, "data": inner}
    return {"data": inner} if wrap_bare else inner
