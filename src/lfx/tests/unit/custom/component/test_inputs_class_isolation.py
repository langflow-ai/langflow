"""Regression: a Component instance must not mutate its class's `inputs` list.

Bug history (May 2026): ``Component._get_or_create_input`` did
``self.inputs.append(input_)`` for any unknown kwarg passed to ``set()``.
``self.inputs`` resolves to the class-level list when no instance attribute
shadows it — so the fallback Input (and its captured value, e.g. a live
``ChatOpenAI`` carrying an httpx Client + RLock) leaked into the class
definition. The next instance, on ``map_inputs``, would try to deepcopy the
polluted class list and raise ``TypeError: cannot pickle '_thread.RLock'``.

These tests pin down the contract: writing to ``self.inputs`` on an instance
must never alter ``type(self).inputs``.
"""

import pytest
from lfx.components.input_output.chat import ChatInput


def _input_names(inputs) -> list[str | None]:
    return [getattr(inp, "name", None) for inp in inputs]


@pytest.fixture
def class_inputs_snapshot():
    """Capture the unpolluted class-level input names before any test instance runs."""
    return _input_names(ChatInput.inputs)


def test_instance_set_with_unknown_key_must_not_mutate_class_inputs(class_inputs_snapshot):
    component = ChatInput()

    component.set(some_unknown_param="hello")

    # Class-level inputs unchanged.
    assert _input_names(ChatInput.inputs) == class_inputs_snapshot


def test_two_instances_share_class_inputs_count_after_unknown_set(class_inputs_snapshot):
    a = ChatInput()
    a.set(temperature=0.1)
    a.set(llm="fake-llm-instance")

    # Second instance constructs cleanly even after the first added unknown keys —
    # this is the regression guard for the deepcopy/RLock crash.
    b = ChatInput()
    assert _input_names(b.inputs) == class_inputs_snapshot
    assert _input_names(ChatInput.inputs) == class_inputs_snapshot


def test_instance_inputs_diverge_from_class_inputs_after_unknown_set(class_inputs_snapshot):
    component = ChatInput()

    component.set(stash_value="instance-only")

    # Instance has the new fallback input...
    assert "stash_value" in _input_names(component.inputs)
    # ...but the class is untouched.
    assert "stash_value" not in _input_names(ChatInput.inputs)
    assert _input_names(ChatInput.inputs) == class_inputs_snapshot
