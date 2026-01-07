from typing import TYPE_CHECKING

from lfx.custom import validate

if TYPE_CHECKING:
    from lfx.custom.custom_component.custom_component import CustomComponent


def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Evaluate custom component code.
    
    Validates the code before executing it to catch security violations early.
    """
    # Validate code first to catch security violations before execution
    validation_errors = validate.validate_code(code)
    if validation_errors["imports"]["errors"] or validation_errors["function"]["errors"]:
        # Format errors for user-friendly display
        error_messages = []
        if validation_errors["imports"]["errors"]:
            error_messages.extend(validation_errors["imports"]["errors"])
        if validation_errors["function"]["errors"]:
            error_messages.extend(validation_errors["function"]["errors"])
        error_msg = "\n".join(str(e) for e in error_messages)
        raise ValueError(f"Code validation failed:\n{error_msg}")
    
    class_name = validate.extract_class_name(code)
    return validate.create_class(code, class_name)
