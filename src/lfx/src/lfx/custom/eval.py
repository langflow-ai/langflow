from typing import TYPE_CHECKING

from lfx.custom import validate

if TYPE_CHECKING:
    from lfx.custom.custom_component.custom_component import CustomComponent


def eval_custom_component_code(
    code: str, class_name: str | None = None, *, reuse_class: bool = False
) -> type["CustomComponent"]:
    """Evaluate custom component code, building ``class_name`` when the source defines several components.

    With ``reuse_class=True`` and ``component_class_cache_enabled`` set, an eligible source returns the class
    built earlier instead of re-executing it. The cache is consulted only after source resolution, so it never
    authorizes code the ordinary path rejects. Callers must create a fresh instance per use.
    """
    from lfx.custom.legacy_storage_compat import resolve_shipped_storage_component

    replacement = resolve_shipped_storage_component(code)
    if replacement is not None:
        return replacement
    resolved_name = validate.extract_class_name(code, class_name)
    if not reuse_class:
        return validate.create_class(code, resolved_name)

    from lfx.custom.class_cache import get_or_build_component_class

    return get_or_build_component_class(code, resolved_name, lambda: validate.create_class(code, resolved_name))
