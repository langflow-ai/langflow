"""create_class builds a component class once, unless the source could see the extra build.

Before this change, prepare_global_scope executed the component class with the
other module-level definitions and create_class then built it a second time,
keeping only the second class. These tests compare the single build against
that double build, which ``_component_class_builds_once`` returning False
still performs.
"""

import ast
import uuid
from textwrap import dedent

import pytest
from lfx.custom import build_once, validate
from lfx.field_typing.constants import DEFAULT_IMPORT_STRING


def _outcome(monkeypatch, code, class_name, observe, *, build_once_decision=None):
    """Create the class with the real decision, or force one, and observe the result."""
    if build_once_decision is not None:
        monkeypatch.setattr(validate, "_component_class_builds_once", lambda *_: build_once_decision)
    try:
        result = ("ok", observe(validate.create_class(code, class_name)))
    except ValueError as exc:
        result = ("error", str(exc))
    monkeypatch.undo()
    return result


def _definitions(code):
    module = ast.parse(DEFAULT_IMPORT_STRING + "\n" + code)
    return [node for node in module.body if isinstance(node, build_once._DEFINITION_TYPES)]


def _describe(component_class):
    """Everything a caller can see of the created class and its module namespace."""
    namespace = component_class.probe.__globals__
    return {
        "mro": [f"{cls.__module__}.{cls.__qualname__}" for cls in component_class.__mro__],
        "attributes": sorted(vars(component_class)),
        "probe": component_class.probe(),
        "namespace": sorted(namespace),
        "binds_class": namespace[component_class.__name__] is component_class,
    }


def test_component_class_body_runs_once(monkeypatch):
    code = dedent("""
    from lfx.custom import Component

    _CREATED = []

    def _record():
        _CREATED.append(1)
        return len(_CREATED)

    class CountingComponent(Component):
        created_as = _record()

        @staticmethod
        def probe():
            return len(_CREATED)
    """)

    assert _outcome(monkeypatch, code, "CountingComponent", lambda cls: (cls.created_as, cls.probe())) == (
        "ok",
        (1, 1),
    )
    assert _outcome(
        monkeypatch, code, "CountingComponent", lambda cls: (cls.created_as, cls.probe()), build_once_decision=False
    ) == ("ok", (2, 2))


SAME_RESULT_SOURCES = {
    "only the class": """
    from lfx.custom import Component

    class ProbeComponent(Component):
        display_name = "Probe"

        @staticmethod
        def probe():
            return "probe"
    """,
    "helpers before the class": """
    from lfx.custom import Component
    from lfx.io import MessageTextInput, Output

    DEFAULT = "value"

    def _default():
        return DEFAULT

    class ProbeComponent(Component):
        inputs = [MessageTextInput(name="text", value=_default())]
        outputs = [Output(name="out", method="probe")]

        @staticmethod
        def probe():
            return _default()
    """,
    "helpers after the class, used only when called": """
    from lfx.custom import Component

    class ProbeComponent(Component):
        @staticmethod
        def probe():
            try:
                raise ProbeError(_stringify(1))
            except ProbeError as exc:
                return str(exc)

    def _stringify(value):
        return str(value)

    class ProbeError(Exception):
        pass
    """,
    "the class names itself only inside methods": """
    from lfx.custom import Component

    class ProbeComponent(Component):
        @staticmethod
        def helper():
            return "helper"

        @staticmethod
        def probe():
            return ProbeComponent.helper()
    """,
    "its own __future__ import": """
    from __future__ import annotations

    from lfx.custom import Component

    class ProbeComponent(Component):
        @staticmethod
        def probe() -> str:
            return ProbeComponent.probe.__annotations__["return"]
    """,
}


@pytest.mark.parametrize("code", SAME_RESULT_SOURCES.values(), ids=SAME_RESULT_SOURCES.keys())
def test_single_build_matches_double_build(monkeypatch, code):
    code = dedent(code)

    assert build_once.first_build_is_unobserved(_definitions(code), "ProbeComponent")
    single = _outcome(monkeypatch, code, "ProbeComponent", _describe)
    double = _outcome(monkeypatch, code, "ProbeComponent", _describe, build_once_decision=False)
    assert single[0] == "ok"
    assert single == double


# Sources whose result depends on the class being built twice. Each one would
# change if the class were built once, so the check must keep both builds.
DOUBLE_BUILD_SOURCES = {
    "a later definition reads the class through globals()": (
        """
        from lfx.custom import Component

        class ProbeComponent(Component):
            pass

        globals()["ProbeComponent"].patched = True
        """,
        lambda cls: getattr(cls, "patched", False),
    ),
    "a later definition names the class": (
        """
        from lfx.custom import Component

        class ProbeComponent(Component):
            pass

        ProbeComponent.patched = True
        """,
        lambda cls: getattr(cls, "patched", False),
    ),
    "a later definition lists the namespace": (
        """
        from lfx.custom import Component

        class ProbeComponent(Component):
            @staticmethod
            def probe():
                return "ProbeComponent" in _NAMES

        _NAMES = dir()
        """,
        lambda cls: cls.probe(),
    ),
    "the class subclasses an import of the same name": (
        """
        from lfx.custom import Component as ProbeComponent

        class ProbeComponent(ProbeComponent):
            pass
        """,
        lambda cls: [base.__qualname__ for base in cls.__mro__[:3]],
    ),
    "the class body reads its own name": (
        """
        from lfx.custom import Component

        class ProbeComponent(Component):
            try:
                previous = ProbeComponent
            except NameError:
                previous = None
        """,
        lambda cls: cls.previous is None,
    ),
    "the class body calls a function that reads the class name": (
        """
        from lfx.custom import Component

        class ProbeComponent(Component):
            def _previous():
                try:
                    return ProbeComponent
                except NameError:
                    return None

            previous = _previous()
        """,
        lambda cls: cls.previous is None,
    ),
    "the class body reads globals()": (
        """
        from lfx.custom import Component

        class ProbeComponent(Component):
            defined_before = "ProbeComponent" in globals()
        """,
        lambda cls: cls.defined_before,
    ),
    "the class body uses a name defined further down": (
        """
        from lfx.custom import Component

        class ProbeComponent(Component):
            value = LATER

        LATER = 1
        """,
        lambda cls: cls.value,
    ),
    "a decorator from the source registers the class": (
        """
        from lfx.custom import Component

        _REGISTERED = []

        def register(cls):
            _REGISTERED.append(cls)
            return cls

        @register
        class ProbeComponent(Component):
            @staticmethod
            def probe():
                return len(_REGISTERED)
        """,
        lambda cls: cls.probe(),
    ),
    "a base class in the source records its subclasses": (
        """
        from lfx.custom import Component

        class RecordingBase(Component):
            created = []

            def __init_subclass__(cls, **kwargs):
                super().__init_subclass__(**kwargs)
                RecordingBase.created.append(cls.__name__)

        class ProbeComponent(RecordingBase):
            pass
        """,
        lambda cls: list(cls.created),
    ),
}


@pytest.mark.parametrize(("code", "observe"), DOUBLE_BUILD_SOURCES.values(), ids=DOUBLE_BUILD_SOURCES.keys())
def test_sources_that_see_the_first_build_keep_both_builds(monkeypatch, code, observe):
    code = dedent(code)

    assert not build_once.first_build_is_unobserved(_definitions(code), "ProbeComponent")
    real = _outcome(monkeypatch, code, "ProbeComponent", observe)
    double = _outcome(monkeypatch, code, "ProbeComponent", observe, build_once_decision=False)
    single = _outcome(monkeypatch, code, "ProbeComponent", observe, build_once_decision=True)
    assert real == double
    assert single != double


def test_decision_is_computed_once_per_source(monkeypatch):
    code = dedent(f"""
    from lfx.custom import Component

    class ProbeComponent(Component):
        source_id = "{uuid.uuid4().hex}"
    """)
    calls = []
    real = build_once.first_build_is_unobserved

    def counting(definitions, class_name):
        calls.append(class_name)
        return real(definitions, class_name)

    monkeypatch.setattr(build_once, "first_build_is_unobserved", counting)

    validate.create_class(code, "ProbeComponent")
    validate.create_class(code, "ProbeComponent")

    assert calls == ["ProbeComponent"]


def test_prepare_global_scope_leaves_out_the_skipped_class():
    module = ast.parse(
        dedent("""
        from __future__ import annotations

        CONSTANT = 1

        class ProbeComponent:
            pass
        """)
    )

    scope = validate.prepare_global_scope(module, source_class_bindings={}, skip_class_name="ProbeComponent")

    assert "ProbeComponent" not in scope
    assert scope["CONSTANT"] == 1
    # The __future__ import still binds its name, as it did when the class ran here.
    assert "annotations" in scope
