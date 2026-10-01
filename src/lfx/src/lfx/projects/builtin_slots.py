"""Built-in contracts, including their lazy adapters to existing flow validators."""

from lfx.projects.registry import register_slot
from lfx.projects.schema import Cardinality, FireTiming, SlotDefinition


class InstructionsSlot(SlotDefinition):
    def binding_contract(self):
        from lfx.projects.bindings import FlowBinding, instruction_outputs, validate_instruction_binding

        return FlowBinding, instruction_outputs, validate_instruction_binding

    def build_baseline(self, initial_value=None, *, initial_config=None):  # noqa: ARG002 -- shared factory interface
        from lfx.projects.baselines import instructions_baseline

        return instructions_baseline(initial_value)


class HookSlot(SlotDefinition):
    def binding_contract(self):
        from lfx.projects.hooks import HookBinding, hook_outputs, validate_hook_binding

        return HookBinding, hook_outputs, validate_hook_binding

    def build_baseline(self, initial_value=None, *, initial_config=None):  # noqa: ARG002 -- shared factory interface
        from lfx.projects.baselines import hook_baseline

        return hook_baseline()


class ContextSlot(SlotDefinition):
    def binding_contract(self):
        from lfx.projects.context import ContextBinding, context_outputs, validate_context_binding

        return ContextBinding, context_outputs, validate_context_binding

    def build_baseline(self, initial_value=None, *, initial_config=None):  # noqa: ARG002 -- shared factory interface
        from lfx.projects.baselines import context_baseline

        return context_baseline(initial_config)


class CompactionSlot(SlotDefinition):
    def binding_contract(self):
        from lfx.projects.compaction import CompactionBinding, compaction_outputs, validate_compaction_binding

        return CompactionBinding, compaction_outputs, validate_compaction_binding

    def build_baseline(self, initial_value=None, *, initial_config=None):  # noqa: ARG002 -- shared factory interface
        from lfx.projects.baselines import compaction_baseline

        return compaction_baseline(initial_config)


class PermissionSlot(SlotDefinition):
    def binding_contract(self):
        from lfx.projects.permissions import PermissionBinding, permission_outputs, validate_permission_binding

        return PermissionBinding, permission_outputs, validate_permission_binding

    def build_baseline(self, initial_value=None, *, initial_config=None):  # noqa: ARG002 -- shared factory interface
        from lfx.projects.baselines import permission_baseline

        return permission_baseline(initial_config)


class ScorerSlot(SlotDefinition):
    def binding_contract(self):
        from lfx.projects.evaluations import FlowBinding, scorer_outputs, validate_scorer

        return FlowBinding, scorer_outputs, validate_scorer


class ToolSlot(SlotDefinition):
    def validate_binding(self, data, binding):
        from lfx.projects.local_tools import LocalToolBinding, validate_local_tool_source

        if not isinstance(binding, LocalToolBinding):
            msg = "This field does not yet support flow bindings."
            raise ValueError(msg)  # noqa: TRY004 -- preserve the existing binding validation error contract
        validate_local_tool_source(data, binding)

    def validation_source(self, source):
        return source


AGENTIC_LOOP = register_slot(SlotDefinition("AgenticLoop", "Message", FireTiming.ORCHESTRATOR))
TOOL = register_slot(ToolSlot("Tool", "Tool", FireTiming.ON_LLM_TOOL_CALL, Cardinality.MULTI))
INSTRUCTIONS = register_slot(
    InstructionsSlot(
        "Instructions",
        "Message",
        FireTiming.ONCE_PER_RUN,
        default_flow_ref="builtin:instructions",
        binding_kind="instructions",
        binding_label="Instructions",
        agent_input_name="system_prompt",
        validation_hint="Configure required inputs and connect a terminal text output.",
        baseline_error_hint="Check the instructions before creating their flow.",
    )
)
HOOK = register_slot(
    HookSlot(
        "Hook",
        "HookDecision",
        FireTiming.ON_EVENT,
        Cardinality.MULTI,
        default_flow_ref="builtin:hook",
        binding_kind="hook",
        binding_label="Hooks",
        agent_input_name="hook_bindings",
        origin_key="_harness_hooks",
        origin_binding_key="bindings",
        validation_hint="Connect one Hook Event to a terminal Hook decision and configure required inputs.",
        baseline_error_hint="Check the hook settings before creating its flow.",
    )
)
CONTEXT_MANAGER = register_slot(
    ContextSlot(
        "ContextManager",
        "DataFrame",
        FireTiming.PER_LLM_CALL,
        default_flow_ref="builtin:context",
        binding_kind="context",
        binding_label="Context",
        agent_input_name="context_binding",
        origin_key="_harness_context",
        initial_config_fields=("context_strategy", "context_turns"),
        validation_hint="Connect one Agent Context to a terminal message Table and configure required inputs.",
        baseline_error_hint="Check the context strategy and recent-turn count before creating its flow.",
    )
)
COMPACTOR = register_slot(
    CompactionSlot(
        "Compactor",
        "CompactionResult",
        FireTiming.ON_THRESHOLD,
        default_flow_ref="builtin:compaction",
        binding_kind="compaction",
        binding_label="Compaction",
        agent_input_name="compaction_binding",
        origin_key="_harness_compaction",
        initial_config_fields=("compaction_trigger_tokens", "compaction_keep_messages"),
        validation_hint="Connect one Compaction Input to a terminal CompactionResult and configure required inputs.",
        baseline_error_hint="Check the compaction threshold and recent-message count before creating its flow.",
    )
)
PERMISSION_GATE = register_slot(
    PermissionSlot(
        "PermissionGate",
        "Permission",
        FireTiming.PER_TOOL_CALL,
        default_flow_ref="builtin:permission",
        binding_kind="permission",
        binding_label="Permissions",
        agent_input_name="permission_binding",
        origin_key="_harness_permission",
        initial_config_fields=("tool_policy",),
        validation_hint="Connect one Permission Request to a terminal Permission output and configure required inputs.",
        baseline_error_hint="Check the tool permission policy before creating its flow.",
    )
)
SCORER = register_slot(ScorerSlot("Scorer", "Data", FireTiming.ON_RESULT))

# Saved harness field identifiers remain stable. Other project types attach these same slots
# to their own fields; generic API discovery resolves the slot from that field declaration.
HARNESS_BINDING_SLOTS = {
    "system_prompt": INSTRUCTIONS,
    "hooks": HOOK,
    "context_strategy": CONTEXT_MANAGER,
    "compaction": COMPACTOR,
    "tool_policy": PERMISSION_GATE,
}
BINDING_SLOTS = {**HARNESS_BINDING_SLOTS, "tools": TOOL, "scorer": SCORER}
