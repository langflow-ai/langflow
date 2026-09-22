"""Project types: the folder-level vocabulary shared by langflow and lfx.

A project type says what a folder of flows *is*, and carries the form the UI renders for it.
It lives in lfx because lfx is the runtime that actually loads a folder off disk, and because
the arrow only runs one way: langflow imports lfx, never the reverse.
"""

from lfx.projects import builtins
from lfx.projects.registry import (
    all_project_types,
    get_project_type,
    register_project_type,
    registered_project_types,
)
from lfx.projects.schema import FieldTarget, ProjectType, ProjectTypeField

DEFAULT_PROJECT_TYPE = builtins.DEFAULT_PROJECT_TYPE

#: The types Langflow ships. Anything outside this set came from a plugin, so the API can tell
#: a user's own type from one it is responsible for.
CORE_PROJECT_TYPES = frozenset({builtins.FLOWS.name, builtins.AGENT_HARNESS.name})

__all__ = [
    "CORE_PROJECT_TYPES",
    "DEFAULT_PROJECT_TYPE",
    "FieldTarget",
    "ProjectType",
    "ProjectTypeField",
    "all_project_types",
    "get_project_type",
    "register_project_type",
    "registered_project_types",
]
