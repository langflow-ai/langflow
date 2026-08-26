from functools import lru_cache
from typing import TYPE_CHECKING

from lfx.custom import validate

if TYPE_CHECKING:
    from lfx.custom.custom_component.custom_component import CustomComponent


# Every vertex build calls this (``initialize.loading.instantiate_class`` ->
# ``Vertex._build``), and a fresh ``Graph`` is constructed per request, so the
# uncached form re-ran ``ast.parse`` + ``prepare_global_scope`` + ``compile`` +
# ``exec`` for every component on every flow run.  Profiling a 4-node flow put
# that at ~10 ms of pure CPU per request -- the single largest term in flow-run
# overhead, and entirely redundant: the component source is identical between
# runs, so the resulting class is too.
#
# Keyed on the source string, which is the same key the component cache already
# hashes on (``custom.utils._generate_code_hash``).  Edited component code is a
# different string and therefore a different entry, so the cache cannot serve a
# stale class.  Callers mutate the *instance* returned by ``class_object(...)``,
# never the class object itself, so sharing the class across builds is safe.
@lru_cache(maxsize=512)
def eval_custom_component_code(code: str) -> type["CustomComponent"]:
    """Evaluate custom component code.

    The compiled class is cached per source string; callers must not mutate
    class-level state on the returned type.
    """
    class_name = validate.extract_class_name(code)
    return validate.create_class(code, class_name)
