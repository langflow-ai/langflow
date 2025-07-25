# Re-export constants from lfx to complete the migration
from lfx.inputs.constants import MAX_TAB_OPTION_LENGTH, MAX_TAB_OPTIONS

__all__ = ["MAX_TAB_OPTIONS", "MAX_TAB_OPTION_LENGTH"]
