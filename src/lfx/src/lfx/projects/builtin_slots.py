"""The harness contracts shared with future project types.

Registration publishes vocabulary, not runtime support. The custom loop still needs a runtime adapter.
Instructions, Hook, ContextManager, Compactor, and PermissionGate publish executable baselines.
"""

from lfx.projects.registry import register_slot
from lfx.projects.schema import Cardinality, FireTiming, SlotDefinition

AGENTIC_LOOP = register_slot(
    SlotDefinition("AgenticLoop", "Message", FireTiming.ORCHESTRATOR),
)
TOOL = register_slot(
    SlotDefinition("Tool", "Tool", FireTiming.ON_LLM_TOOL_CALL, Cardinality.MULTI),
)
HOOK = register_slot(
    SlotDefinition("Hook", "HookDecision", FireTiming.ON_EVENT, Cardinality.MULTI, default_flow_ref="builtin:hook"),
)
SYSTEM_PROMPT_BUILDER = register_slot(
    SlotDefinition("SystemPromptBuilder", "str", FireTiming.ONCE_PER_RUN, default_flow_ref="builtin:instructions"),
)
CONTEXT_MANAGER = register_slot(
    SlotDefinition("ContextManager", "DataFrame", FireTiming.PER_LLM_CALL, default_flow_ref="builtin:context"),
)
COMPACTOR = register_slot(
    SlotDefinition("Compactor", "CompactionResult", FireTiming.ON_THRESHOLD, default_flow_ref="builtin:compaction"),
)
PERMISSION_GATE = register_slot(
    SlotDefinition("PermissionGate", "Permission", FireTiming.PER_TOOL_CALL, default_flow_ref="builtin:permission"),
)
