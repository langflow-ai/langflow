# Re-export validators from lfx to complete the migration
from lfx.inputs.validators import CoalesceBool, validate_boolean

__all__ = ["CoalesceBool", "validate_boolean"]
