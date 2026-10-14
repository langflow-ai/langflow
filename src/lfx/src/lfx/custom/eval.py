from typing import TYPE_CHECKING

from lfx.custom import validate

if TYPE_CHECKING:
    from lfx.custom.custom_component.custom_component import CustomComponent


def eval_custom_component_code(code: str, class_name: str | None = None) -> type["CustomComponent"]:
    """Evaluate custom component code, building ``class_name`` when the source defines several components."""
    from lfx.custom.legacy_storage_compat import resolve_shipped_storage_component

    replacement = resolve_shipped_storage_component(code)
    if replacement is not None:
        return replacement
    return validate.create_class(code, validate.extract_class_name(code, class_name))
