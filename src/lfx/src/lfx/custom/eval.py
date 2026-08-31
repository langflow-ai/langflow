from typing import TYPE_CHECKING

from lfx.custom import validate

if TYPE_CHECKING:
    from lfx.custom.custom_component.custom_component import CustomComponent


def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Build the component class from its source.

    The source used to be AST-parsed twice (extract_class_name, then
    create_class), compiled, and exec'd on every call -- for every vertex of
    every flow build, measured at ~22% of CPU on a saturated worker.

    An lru_cache on this function was tried and REVERTED: it is a cross-tenant
    data leak. Caching makes every instantiation of byte-identical source share
    ONE class object, so any class-level mutable state persists across requests.
    Reproduced live -- a component with a `_seen = []` class attribute (the
    classic mutable-default mistake, and Langflow targets non-expert Python
    users) had one tenant's input appear in another tenant's output, silently.
    It does not even need two tenants: sibling vertices in one graph layer build
    concurrently via asyncio.gather, so a single flow containing two copies of
    the same component hits it.

    This now caches the parsed/compiled artefacts (immutable: a class name and
    two code objects) via validate._compile_component_artifacts, and exec's a
    FRESH class from them on every call via validate._instantiate_component_class
    -- exec is what creates the isolated class object, and nothing mutable is
    ever shared. See validate.py's "Cached compile path" section and
    test_component_class_isolation.py, which enforces this guarantee directly.
    """
    artifacts = validate._compile_component_artifacts(code)  # noqa: SLF001
    return validate._instantiate_component_class(artifacts)  # noqa: SLF001
