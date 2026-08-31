"""Cover the cached compile path added to recover eval_custom_component_code's CPU cost.

test_component_class_isolation.py is the mandatory isolation gate and must not be
touched. This file covers two things that gate doesn't:

1. That the cache in validate._compile_component_artifacts is actually being hit
   (i.e. the optimization is real, not a no-op).
2. That isolation also holds for module-level definitions (helper functions,
   assignments) referenced by the component -- those are compiled into a second
   cached artifact (definitions_code_obj) that this file's own tests exercise
   but test_component_class_isolation.py's LEAKY_SOURCE does not.
"""

from lfx.custom import validate
from lfx.custom.eval import eval_custom_component_code

LEAKY_SOURCE = """
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class LeakyComponent(Component):
    display_name = "Leaky"
    description = "holds class-level mutable state"
    _seen = []

    inputs = [MessageTextInput(name="input_value", display_name="In")]
    outputs = [Output(display_name="Out", name="out", method="process")]

    def process(self) -> Message:
        self._seen.append(self.input_value)
        return Message(text=f"seen={self._seen}")
"""

HELPER_SOURCE = """
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message

_module_level_calls = []


def helper(value):
    _module_level_calls.append(value)
    return f"helper-saw={_module_level_calls}"


class HelperComponent(Component):
    display_name = "Helper"
    inputs = [MessageTextInput(name="input_value", display_name="In")]
    outputs = [Output(display_name="Out", name="out", method="process")]

    def process(self) -> Message:
        return Message(text=helper(self.input_value))
"""


def test_compile_artifacts_are_actually_cached():
    """The optimization only matters if the parse/compile step is skipped on repeat calls."""
    validate._compile_component_artifacts.cache_clear()

    eval_custom_component_code(LEAKY_SOURCE)
    info = validate._compile_component_artifacts.cache_info()
    assert info.misses == 1
    assert info.hits == 0

    eval_custom_component_code(LEAKY_SOURCE)
    eval_custom_component_code(LEAKY_SOURCE)
    info = validate._compile_component_artifacts.cache_info()
    assert info.misses == 1, "identical source should not be re-parsed/re-compiled"
    assert info.hits == 2


def test_module_level_helper_state_does_not_leak_between_instantiations():
    """Confirm module-level defs (functions/assignments) are isolated too.

    Those are compiled into a separate cached artifact (definitions_code_obj)
    from the class itself. Confirm that artifact's cached code object still
    produces fresh, isolated module-level state on every call -- not just the
    class object.
    """
    first_cls = eval_custom_component_code(HELPER_SOURCE)
    second_cls = eval_custom_component_code(HELPER_SOURCE)

    first_cls(input_value="tenant-A-secret").process()
    second_output = second_cls(input_value="tenant-B-value").process().text

    assert "tenant-A-secret" not in second_output, (
        f"module-level helper state leaked across instantiations: {second_output!r}"
    )


def test_distinct_sources_get_distinct_cache_entries():
    """Sanity check that the cache key is source-sensitive, not a blanket singleton."""
    validate._compile_component_artifacts.cache_clear()

    eval_custom_component_code(LEAKY_SOURCE)
    eval_custom_component_code(HELPER_SOURCE)

    info = validate._compile_component_artifacts.cache_info()
    assert info.misses == 2
    assert info.currsize == 2
