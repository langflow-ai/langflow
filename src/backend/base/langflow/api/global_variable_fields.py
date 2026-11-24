"""Pure field-shape helpers shared by API execution paths.

This module deliberately lives outside ``langflow.api.v1``. Importing a v1
submodule executes ``langflow.api.v1.__init__``, which registers the v1 routers;
low-level execution helpers must not depend on that router initialization path.
"""

from __future__ import annotations

from typing import Any

from lfx.utils.constants import DIRECT_TYPES

# Field ``type`` values that should be considered for automatic global-variable
# binding. Mirrors what the frontend's ``StrRenderComponent`` actually delegates
# to ``InputGlobalComponent`` -- str-like inputs without options. Other DIRECT_TYPES
# entries (dict, code, table, NestedDict, sortableList, ...) never render the
# global-variable picker, so they are intentionally excluded.
_GLOBAL_VARIABLE_ELIGIBLE_TYPES: frozenset[str] = frozenset({"str"})


def is_global_variable_eligible_field(field: Any) -> bool:
    """Return whether a template field can accept an auto-bound global variable."""
    if not isinstance(field, dict):
        return False
    # Field must be visible (mirrors frontend rendering gate) and a text-ish input.
    if field.get("show") is False:
        return False
    field_type = field.get("type")
    if field_type not in DIRECT_TYPES or field_type not in _GLOBAL_VARIABLE_ELIGIBLE_TYPES:
        return False
    # Don't clobber an explicit user choice already persisted to the template.
    if field.get("load_from_db") is True:
        return False
    # Only fill empty fields -- never overwrite a real value.
    existing = field.get("value")
    return existing in (None, "")
