"""Opt-in, process-local in-memory flow-graph registry.

Holds bounded structural ``Graph`` templates for eligible v1/v2 sync runs. Every
request still performs its normal authentication/authorization and revision checks;
stream, background, public, and request-mutated runs stay cold. Each machine keeps
resident entries current against the shared ``flow`` table without Redis.
"""

from langflow.services.warm_registry.service import WarmGraphRegistry, get_warm_registry

__all__ = ["WarmGraphRegistry", "get_warm_registry"]
