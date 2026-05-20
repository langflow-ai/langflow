from lfx.execution import (
    Coordinator,
    get_default_coordinator,
    get_default_registry,
    set_default_coordinator,
)


def test_default_registry_has_in_process():
    assert get_default_registry().get("in-process").kind == "in-process"


def test_default_coordinator_uses_default_registry():
    c = get_default_coordinator()
    assert isinstance(c, Coordinator)


def test_set_default_coordinator_overrides_singleton():
    custom = Coordinator(registry=get_default_registry())
    set_default_coordinator(custom)
    assert get_default_coordinator() is custom


def test_default_coordinator_is_idempotent_within_a_test():
    a = get_default_coordinator()
    b = get_default_coordinator()
    assert a is b
