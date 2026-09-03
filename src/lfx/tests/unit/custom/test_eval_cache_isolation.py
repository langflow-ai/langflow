"""State-isolation guarantees for the cached component-class compiler.

``eval_custom_component_code`` caches the compiled class per source string, so a
single class object is now shared by every vertex and every request that uses
that source.  That is only safe while nothing mutates class-level state, and
Langflow has been bitten by exactly that before -- see the comment in
``Component.__getattr__`` about appending to ``self.inputs`` leaking "a live LLM
client into every future instance".

These tests pin the invariant down.  The load-bearing one is
``test_leak_detector_catches_deliberate_class_mutation``: it builds a component
that genuinely leaks and asserts the detector notices.  Without it the rest of
this module could pass vacuously -- a green suite would prove only that the
detector never fires, not that the components are clean.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import importlib
import inspect
import pkgutil
import textwrap

import pytest
from lfx.custom.custom_component.component import Component
from lfx.custom.eval import eval_custom_component_code

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def class_state(cls: type) -> dict:
    """Deep snapshot of every mutable attribute reachable on ``cls``.

    Uses ``getattr_static`` so descriptors and properties are not executed --
    we want the stored class attribute, not whatever a property would compute.
    """
    snapshot: dict = {}
    for key in dir(cls):
        if key.startswith("__"):
            continue
        try:
            value = inspect.getattr_static(cls, key)
        except Exception:  # noqa: S112 - unreadable attrs cannot leak state
            continue
        if isinstance(value, (list, dict, set)):
            try:
                snapshot[key] = copy.deepcopy(value)
            except Exception:
                snapshot[key] = repr(value)
    return snapshot


def drifted(cls: type, before: dict) -> list[str]:
    """Attribute names whose class-level value changed since ``before``."""
    after = class_state(cls)
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


SIMPLE_SOURCE = """
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.schema.message import Message
from lfx.template.field.base import Output


class IsolationProbeComponent(Component):
    display_name = "Isolation Probe"
    name = "IsolationProbe"
    inputs = [MessageTextInput(name="text", display_name="Text")]
    outputs = [Output(display_name="Out", name="out", method="run")]

    def run(self) -> Message:
        return Message(text=self.text or "")
"""

# Same component, different display_name -> a genuinely different source string.
VARIANT_SOURCE = SIMPLE_SOURCE.replace('"Isolation Probe"', '"Isolation Probe Variant"')

# A component that DOES leak: ``registry`` is a mutable class attribute that is
# never shadowed on the instance, so ``self.registry.append`` mutates the class.
LEAKY_SOURCE = """
from lfx.custom.custom_component.component import Component
from lfx.schema.message import Message
from lfx.template.field.base import Output


class LeakyProbeComponent(Component):
    display_name = "Leaky Probe"
    name = "LeakyProbe"
    registry: list = []
    inputs = []
    outputs = [Output(display_name="Out", name="out", method="run")]

    def run(self) -> Message:
        self.registry.append("leaked")
        return Message(text="")
"""


# --------------------------------------------------------------------------
# the cache itself
# --------------------------------------------------------------------------


def test_identical_source_yields_the_same_class_object():
    """The whole point of the cache: one compile per distinct source."""
    first = eval_custom_component_code(SIMPLE_SOURCE)
    second = eval_custom_component_code(SIMPLE_SOURCE)

    assert first is second


def test_distinct_sources_yield_distinct_class_objects():
    """Two different components must never collapse onto one cached class."""
    probe = eval_custom_component_code(SIMPLE_SOURCE)
    variant = eval_custom_component_code(VARIANT_SOURCE)

    assert probe is not variant
    assert probe.display_name == "Isolation Probe"
    assert variant.display_name == "Isolation Probe Variant"


def test_edited_source_is_never_served_from_cache():
    """Editing a component in the UI changes the source, so it must recompile."""
    original = eval_custom_component_code(SIMPLE_SOURCE)
    edited_source = SIMPLE_SOURCE.replace("self.text or ''", "self.text or 'edited'")
    edited_source = edited_source.replace('display_name = "Isolation Probe"', 'display_name = "Edited"')

    edited = eval_custom_component_code(edited_source)

    assert edited is not original
    assert edited.display_name == "Edited"


# --------------------------------------------------------------------------
# the detector has teeth
# --------------------------------------------------------------------------


def test_leak_detector_catches_deliberate_class_mutation():
    """Proves the isolation assertions below can actually fail.

    ``LeakyProbeComponent.registry`` is a class-level list the component mutates
    in place.  If this test ever goes green-by-accident -- i.e. ``drifted``
    reports nothing here -- then every other isolation test in this module is
    worthless, because the detector cannot see a leak even when one is staring
    at it.
    """
    leaky = eval_custom_component_code(LEAKY_SOURCE)
    before = class_state(leaky)

    instance = leaky()
    instance.run()

    changes = drifted(leaky, before)
    assert "registry" in changes, (
        "the leak detector failed to notice a deliberate class-level mutation; "
        "the isolation tests in this module cannot be trusted"
    )
    # And the leak is visible to a *separate* instance -- the real damage.
    assert "leaked" in leaky().registry


# --------------------------------------------------------------------------
# the invariant
# --------------------------------------------------------------------------


def test_instantiating_a_component_does_not_mutate_its_class():
    probe = eval_custom_component_code(SIMPLE_SOURCE)
    before = class_state(probe)

    probe()
    probe()

    assert drifted(probe, before) == []


def test_instance_input_mutation_does_not_leak_to_the_class():
    """The specific hazard documented in ``Component._get_or_create_input``.

    Setting an undeclared field installs a *fallback input*; that must land on
    the instance, never on the shared class-level ``inputs`` list.  Before the
    guard in ``_get_or_create_input`` this appended straight onto the class.
    """
    probe = eval_custom_component_code(SIMPLE_SOURCE)
    before = class_state(probe)

    instance = probe()
    instance.set(some_undeclared_field="value")  # -> _get_or_create_input fallback
    instance.inputs.append("instance-only")

    assert drifted(probe, before) == []
    assert "instance-only" not in probe.inputs


def test_two_instances_of_one_cached_class_do_not_share_input_state():
    """Same class object, independent instances."""
    probe = eval_custom_component_code(SIMPLE_SOURCE)

    a, b = probe(), probe()
    a.inputs.append("only-on-a")

    assert a.inputs is not b.inputs
    assert "only-on-a" not in b.inputs
    assert type(a) is type(b)  # they really are sharing the cached class


def test_repeated_instantiation_does_not_accumulate_class_state():
    """Twenty instances must leave the class exactly as they found it."""
    probe = eval_custom_component_code(SIMPLE_SOURCE)
    before = class_state(probe)

    for index in range(20):
        instance = probe()
        instance.set(text=f"run-{index}")

    assert drifted(probe, before) == []


# --------------------------------------------------------------------------
# the whole component library
# --------------------------------------------------------------------------


def _bundled_component_classes() -> dict[str, type]:
    import lfx.components as components_pkg

    found: dict[str, type] = {}
    for module_info in pkgutil.walk_packages(components_pkg.__path__, components_pkg.__name__ + "."):
        try:
            module = importlib.import_module(module_info.name)
        except Exception:  # noqa: S112 - optional bundles may not be installed
            continue
        for obj in vars(module).values():
            if inspect.isclass(obj) and issubclass(obj, Component) and obj is not Component:
                found[f"{obj.__module__}.{obj.__name__}"] = obj
    return found


def test_no_bundled_component_mutates_its_class_on_instantiation():
    """Sweep every importable component; none may dirty its own class."""
    classes = _bundled_component_classes()
    assert len(classes) > 50, f"expected a substantial component library, found {len(classes)}"

    offenders = []
    checked = 0
    for name, cls in classes.items():
        before = class_state(cls)
        try:
            instance = cls()
        except Exception:  # noqa: S112 - components needing config are out of scope
            continue
        checked += 1
        with contextlib.suppress(Exception):  # build errors are not our concern, mutation is
            instance.to_frontend_node()
        if drifted(cls, before):
            offenders.append((name, drifted(cls, before)))

    assert checked > 50, f"only {checked} components were instantiable; the sweep proves little"
    assert offenders == [], f"components mutated their own class state: {offenders}"


def test_no_bundled_component_declares_a_mutable_class_attribute_it_mutates():
    """Static backstop for components the sweep above cannot instantiate.

    A component is unsafe to share only if it both declares a mutable class
    attribute and mutates it in place.  ``inputs``/``outputs`` are exempt:
    ``Component.__init__`` deep-copies them onto the instance before any user
    code runs.
    """
    mutating_calls = {"append", "extend", "insert", "update", "setdefault", "pop", "clear", "add", "remove"}
    offenders = []

    for name, cls in _bundled_component_classes().items():
        mutable_attrs = {
            key
            for key, value in vars(cls).items()
            if isinstance(value, (list, dict, set)) and key not in {"inputs", "outputs"}
        }
        if not mutable_attrs:
            continue
        try:
            source = inspect.getsource(cls)
            tree = ast.parse(textwrap.dedent(source))
        except (OSError, TypeError, SyntaxError):
            # No retrievable/parseable source (C extension, nested class, exec'd
            # module). The runtime sweep above still covers these.
            continue
        for node in ast.walk(tree):
            # self.<attr>.<mutator>(...)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in mutating_calls
                and isinstance(node.func.value, ast.Attribute)
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "self"
                and node.func.value.attr in mutable_attrs
            ):
                offenders.append(f"{name}: self.{node.func.value.attr}.{node.func.attr}()")
            # self.<attr>[...] = ...
            if isinstance(node, ast.Assign):
                offenders.extend(
                    f"{name}: self.{target.value.attr}[...] = ..."
                    for target in node.targets
                    if isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and isinstance(target.value.value, ast.Name)
                    and target.value.value.id == "self"
                    and target.value.attr in mutable_attrs
                )

    assert offenders == [], f"components mutate a shared class-level attribute in place: {offenders}"


@pytest.mark.parametrize("source", [SIMPLE_SOURCE, VARIANT_SOURCE])
def test_cached_class_survives_being_used_by_many_independent_instances(source):
    """End-to-end: the shared class must behave like a fresh one every time."""
    cls = eval_custom_component_code(source)
    before = class_state(cls)

    results = []
    for index in range(10):
        instance = cls()
        instance.set(text=f"value-{index}")
        results.append(instance.run().text)

    assert results == [f"value-{index}" for index in range(10)]
    assert drifted(cls, before) == []
