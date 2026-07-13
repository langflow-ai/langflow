"""Langflow chat-message memory: the converged lfx Tier 2 service.

Langflow no longer defines its own memory service class. It *selects* lfx's
``DatabaseMemoryService`` and wires it over langflow's Tier 1 ``DatabaseService``
(done in ``langflow.services.utils.register_all_service_factories``). This module
re-exports the lfx class for any code that imported the langflow path.
"""

from lfx.services.memory.database import DatabaseMemoryService

__all__ = ["DatabaseMemoryService"]
