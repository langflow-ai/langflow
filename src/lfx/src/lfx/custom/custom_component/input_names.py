from collections.abc import Iterable
from typing import Any


def input_names_shadowed_by_methods(component_cls: type, inputs: Iterable[Any]) -> set[str]:
    """Input names that normal attribute lookup resolves to a method before `__getattr__` runs.

    `Component.__getattr__` serves an input's value only when normal lookup fails, so an input
    named `index` made `self.index` return the inherited method instead of the configured value.
    Properties and plain class attributes are not reported: built-in components already use names
    such as `code`, `flow_name`, `description` and `inputs`. Only the class MRO is consulted, since
    instance lookup never reaches the metaclass (e.g. `mro`).
    """
    shadowed: set[str] = set()
    for input_ in inputs:
        name = getattr(input_, "name", None)
        if not name:
            continue
        member = next((vars(klass)[name] for klass in component_cls.__mro__ if name in vars(klass)), None)
        if member is not None and not isinstance(member, property) and callable(getattr(component_cls, name)):
            shadowed.add(name)
    return shadowed


def ensure_inputs_not_shadowed_by_methods(component_cls: type, inputs: Iterable[Any]) -> None:
    if shadowed := input_names_shadowed_by_methods(component_cls, inputs):
        names = ", ".join(f"'{name}'" for name in sorted(shadowed))
        msg = (
            f"{component_cls.__name__} has input(s) {names} named after a method of the component, "
            "so `self.<name>` would return the method instead of the configured value. Rename the input."
        )
        raise ValueError(msg)
