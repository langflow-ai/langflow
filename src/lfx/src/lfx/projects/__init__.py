"""Project types: the folder-level vocabulary shared by langflow and lfx.

A project type says what a folder of flows *is*, and carries the form the UI renders for it.
It lives in lfx because lfx is the runtime that actually loads a folder off disk, and because
the arrow only runs one way: langflow imports lfx, never the reverse.
"""

from lfx.projects import builtins
from lfx.projects.registry import (
    all_project_types,
    all_slots,
    get_project_type,
    get_slot,
    register_project_type,
    register_slot,
    registered_project_types,
    registered_slots,
)
from lfx.projects.schema import Cardinality, FieldTarget, FireTiming, ProjectType, ProjectTypeField, SlotDefinition
from lfx.projects.writer import ConfigWrite, apply_project_config

DEFAULT_PROJECT_TYPE = builtins.DEFAULT_PROJECT_TYPE

#: The types Langflow ships. Anything outside this set came from a plugin, so the API can tell
#: a user's own type from one it is responsible for.
CORE_PROJECT_TYPES = frozenset(
    {builtins.FLOWS.name, builtins.AGENT_HARNESS.name, builtins.TOOL_PACK.name, builtins.SKILL_PACK.name}
)

__all__ = [
    "CORE_PROJECT_TYPES",
    "DEFAULT_PROJECT_TYPE",
    "Cardinality",
    "ConfigWrite",
    "FieldTarget",
    "FireTiming",
    "ProjectType",
    "ProjectTypeField",
    "SlotDefinition",
    "all_project_types",
    "all_slots",
    "apply_project_config",
    "get_project_type",
    "get_slot",
    "register_project_type",
    "register_slot",
    "registered_project_types",
    "registered_slots",
]
