"""Versioned tri-state integration policy contract.

Old replicas do not expose this path, so a deny-all write cannot accidentally
reach a server that interprets an empty list as unrestricted.
"""

from langflow.api.v1.policy_bundle import router_v2 as router

__all__ = ["router"]
