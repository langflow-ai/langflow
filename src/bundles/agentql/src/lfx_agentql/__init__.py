"""lfx-agentql: Agentql bundle.

Distribution unit ``lfx-agentql``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:agentql:<Class>@official``.
"""

from lfx_agentql.components.agentql.agentql_api import AgentQL

__all__ = [
    "AgentQL",
]
