from typing import TYPE_CHECKING

from lfx.custom import validate

if TYPE_CHECKING:
    from lfx.custom.custom_component.custom_component import CustomComponent


def eval_custom_component_code(code: str, *, sandbox: bool = False) -> type["CustomComponent"]:
    """Evaluate custom component code.

    Args:
        code: Python source code defining a custom component class.
        sandbox: When True, apply security sandbox restrictions to prevent
                 arbitrary code execution. Should be True during validation
                 (template building) and False during runtime (flow execution).
    """
    class_name = validate.extract_class_name(code)
    return validate.create_class(code, class_name, sandbox=sandbox)
