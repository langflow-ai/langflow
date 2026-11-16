"""Component imports must stay in the component's own exec namespace, never in ``lfx.custom.validate``."""

import pytest
from lfx.custom import validate

HEADER = """
from lfx.custom.custom_component.component import Component
from lfx.io import Output
"""


def component(name: str, imports: str = "", body: str = "return 1") -> str:
    return (
        HEADER
        + imports
        + f"""

class {name}(Component):
    outputs = [Output(name="out", display_name="Out", method="run")]

    def run(self):
        {body}
"""
    )


def test_imports_do_not_leak_into_later_components():
    validate.create_class(component("LeakA", "import fractions as leak_probe_x\n"), "LeakA")
    assert "leak_probe_x" not in vars(validate)
    # The class body is evaluated at build time, so the NameError surfaces there (wrapped as ValueError).
    source = component("LeakB").replace("    def run(self):", "    marker = leak_probe_x\n\n    def run(self):")
    with pytest.raises(ValueError, match="leak_probe_x"):
        validate.create_class(source, "LeakB")


def test_leaked_name_not_visible_at_call_time_to_other_component():
    validate.create_class(component("LeakC", "import fractions as leak_probe_y\n"), "LeakC")
    other = validate.create_class(component("LeakD", body="return leak_probe_y"), "LeakD")
    with pytest.raises(NameError):
        other().run()


def test_component_cannot_rebind_validate_logger():
    original = validate.logger
    validate.create_class(component("LoggerRebind", "import json as logger\n"), "LoggerRebind")
    assert validate.logger is original
    assert not hasattr(validate.logger, "loads")


def test_methods_use_their_own_imports_at_call_time():
    cls = validate.create_class(
        component(
            "OwnImports",
            "import fractions as frac_mod\nimport json as json_alias\n",
            "return str(frac_mod.Fraction(1, 2)) + json_alias.dumps([1])",
        ),
        "OwnImports",
    )
    assert cls().run() == "1/2[1]"
    assert "frac_mod" not in vars(validate)


def test_create_function_does_not_write_back_imports():
    func = validate.create_function(
        "import fractions as leak_probe_fn\n\ndef f():\n    return str(leak_probe_fn.Fraction(1, 3))\n", "f"
    )
    assert func() == "1/3"
    assert "leak_probe_fn" not in vars(validate)


def test_exec_namespaces_are_independent_copies():
    one, two = validate._new_exec_globals(), validate._new_exec_globals()
    one["scratch"] = 1
    assert "scratch" not in two
    assert "scratch" not in validate._new_exec_globals()
