"""Component code validation."""

from lfx.custom.validate import create_class, extract_class_name

from langflow.agentic.api.schemas import ValidationResult


def validate_component_code(code: str) -> ValidationResult:
    """Validate component code by attempting to create the class."""
    try:
        class_name = extract_class_name(code)
        create_class(code, class_name)

        return ValidationResult(is_valid=True, code=code, class_name=class_name)
    except (
        ValueError,
        TypeError,
        SyntaxError,
        NameError,
        ModuleNotFoundError,
        AttributeError,
        ImportError,
        RuntimeError,
        KeyError,
    ) as e:
        return ValidationResult(is_valid=False, code=code, error=f"{type(e).__name__}: {e}")
