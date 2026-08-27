
"""Each component instantiation must get its own class object.

An lru_cache was once added to eval_custom_component_code to remove the ~22% of
CPU spent parsing and compiling component source on every vertex build. It was
reverted: caching the CLASS means every instantiation of byte-identical source
shares one class object, so class-level mutable state persists across requests
and one tenant's data appears in another's output -- silently, with no error.

These tests exist so that optimization cannot be reintroduced without noticing.
A future version may cache the parsed or compiled artefact, but it must exec a
fresh class per call; if these fail, the isolation guarantee is gone.
"""

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


def test_identical_source_yields_distinct_classes():
    """Two builds of the same source must NOT return the same class object."""
    first = eval_custom_component_code(LEAKY_SOURCE)
    second = eval_custom_component_code(LEAKY_SOURCE)

    assert first is not second, (
        "identical source returned the same class object -- class-level state is now "
        "shared between every instantiation, which leaks data across requests"
    )


def test_class_level_state_does_not_leak_between_instances():
    """The concrete failure: one instance's input appearing in another's output.

    Written as the data-leak it actually is rather than an identity check, so it
    keeps failing even if the caching is reintroduced in a different shape.
    """
    cls_a = eval_custom_component_code(LEAKY_SOURCE)
    cls_b = eval_custom_component_code(LEAKY_SOURCE)

    first = cls_a(input_value="tenant-A-secret")
    first.process()
    second_output = cls_b(input_value="tenant-B-value").process().text

    assert "tenant-A-secret" not in second_output, (
        f"one component instance can see another's data: {second_output!r}"
    )


def test_state_is_isolated_within_a_single_build_too():
    """Not only cross-request: sibling vertices in one graph layer build concurrently.

    A single flow containing two copies of the same component is enough to hit
    this, so isolation must hold even without a second tenant.
    """
    cls = eval_custom_component_code(LEAKY_SOURCE)
    sibling = eval_custom_component_code(LEAKY_SOURCE)

    cls(input_value="first-vertex").process()
    out = sibling(input_value="second-vertex").process().text

    assert "first-vertex" not in out, f"sibling vertices share class state: {out!r}"
