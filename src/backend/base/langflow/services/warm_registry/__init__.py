"""Warm in-memory flow-graph registry for ``--backend-only`` PROD execution machines.

Holds pre-parsed ``Graph`` templates per flow so the workflow run path serves a
deepcopy instead of rebuilding from the DB on every request. Kept fresh fleet-wide
with no Redis: each machine reconciles its registry against the shared ``flow``
table (add new / swap changed / evict deleted). See ``service`` and ``reconcile``.
"""

from langflow.services.warm_registry.service import WarmGraphRegistry, get_warm_registry

__all__ = ["WarmGraphRegistry", "get_warm_registry"]
