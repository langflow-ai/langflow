from typing import TYPE_CHECKING

from lfx.custom import validate

if TYPE_CHECKING:
    from lfx.custom.custom_component.custom_component import CustomComponent


def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Build the component class from its source.

    This is expensive -- the source is AST-parsed twice (extract_class_name, then
    create_class), compiled, and exec'd -- and it runs for every vertex of every
    flow build, measured at ~22% of CPU on a saturated worker.

    An lru_cache on this function was tried and REVERTED: it is a cross-tenant
    data leak. Caching makes every instantiation of byte-identical source share
    ONE class object, so any class-level mutable state persists across requests.
    Reproduced live -- a component with a `_seen = []` class attribute (the
    classic mutable-default mistake, and Langflow targets non-expert Python
    users) had one tenant's input appear in another tenant's output, silently.
    It does not even need two tenants: sibling vertices in one graph layer build
    concurrently via asyncio.gather, so a single flow containing two copies of
    the same component hits it.

    Any future attempt must keep per-instantiation isolation. Caching the parsed
    or compiled artefact and exec'ing a FRESH class per call is the promising
    shape, since exec is what creates the isolated class object; caching the
    class itself is not safe.
    """
    class_name = validate.extract_class_name(code)
    return validate.create_class(code, class_name)
