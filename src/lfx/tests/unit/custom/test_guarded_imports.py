"""Custom components may guard optional imports with ``try/except ImportError``.

``prepare_global_scope`` builds the exec scope from top-level imports and definitions.
A guarded import lives inside an ``ast.Try`` node, so it used to be skipped and the
imported name was undefined (``NameError``) when the class body or a method used it.
"""

import pytest
from lfx.custom.validate import create_class

HEADER = """
from lfx.custom.custom_component.component import Component
from lfx.io import Output
"""

COMPONENT = """
class GuardedComp(Component):
    display_name = "Guarded"
    outputs = [Output(display_name="Out", name="out", method="build_out")]
{extra}
    def build_out(self) -> str:
        return str({expr})
"""


def _build(guard: str, expr: str, extra: str = ""):
    code = HEADER + guard + COMPONENT.format(expr=expr, extra=extra)
    return create_class(code, "GuardedComp")


def test_guarded_import_available_in_method():
    cls = _build(
        "try:\n    from decimal import Decimal\nexcept ImportError:\n    Decimal = None\n",
        'Decimal("1.5")',
    )
    assert cls().build_out() == "1.5"


def test_guarded_import_available_in_class_body():
    cls = _build(
        "try:\n    from decimal import Decimal\nexcept ImportError:\n    Decimal = None\n",
        "self.LIMIT",
        extra='    LIMIT = Decimal("2")\n',
    )
    assert str(cls.LIMIT) == "2"


def test_guarded_plain_import_with_alias():
    cls = _build(
        "try:\n    import fractions as alias_one\nexcept ImportError:\n    alias_one = None\n",
        "alias_one.Fraction(1, 2)",
    )
    assert cls().build_out() == "1/2"


def test_missing_optional_module_runs_fallback_assignment():
    cls = _build(
        "try:\n    import no_such_module_xyz_123 as opt_with_fallback\n"
        "except ImportError:\n    opt_with_fallback = None\n",
        "opt_with_fallback is None",
    )
    assert cls().build_out() == "True"


def test_missing_optional_module_runs_fallback_import():
    cls = _build(
        "try:\n    import no_such_module_xyz_123 as mod_fb\nexcept ImportError:\n    import fractions as mod_fb\n",
        "mod_fb.Fraction(3, 4)",
    )
    assert cls().build_out() == "3/4"


def test_missing_optional_module_without_fallback_name_is_still_undefined():
    cls = _build(
        "try:\n    import no_such_module_xyz_123 as opt_no_fallback\nexcept ImportError:\n    pass\n",
        "opt_no_fallback",
    )
    with pytest.raises(NameError):
        cls().build_out()


def test_try_block_with_arbitrary_code_is_still_not_executed():
    """Only import-only guards run; other top-level ``try`` blocks keep being ignored."""
    guard = 'try:\n    leaked = __import__("os").getcwd()\nexcept Exception:\n    pass\n'
    with pytest.raises(ValueError, match="leaked"):
        _build(guard, "1", extra="    VALUE = leaked\n")


def test_guard_with_call_in_handler_is_not_executed():
    guard = (
        "try:\n    import fractions as unused_guard_name\n"
        'except ImportError:\n    unused_guard_name = __import__("os").getcwd()\n'
    )
    # The handler is not trivial, so the whole guard is ignored and the name stays undefined.
    with pytest.raises(ValueError, match="unused_guard_name"):
        _build(guard, "1", extra="    VALUE = unused_guard_name\n")


def test_call_in_handler_exception_expression_is_not_executed():
    guard = "try:\n    import fractions as unused_chain_name\nexcept __import__('os').getcwd().Error:\n    pass\n"
    with pytest.raises(ValueError, match="unused_chain_name"):
        _build(guard, "1", extra="    VALUE = unused_chain_name\n")


def test_dotted_exception_type_is_accepted():
    cls = _build(
        "import builtins\n"
        "try:\n    import no_such_module_xyz_123 as dotted_opt\n"
        "except builtins.ImportError:\n    dotted_opt = None\n",
        "dotted_opt is None",
    )
    assert cls().build_out() == "True"


def test_later_ordinary_import_overrides_guarded_binding():
    cls = _build(
        "try:\n    import decimal as order_a\nexcept ImportError:\n    order_a = None\nimport fractions as order_a\n",
        "order_a.Fraction(1, 3)",
    )
    assert cls().build_out() == "1/3"


def test_later_guarded_import_overrides_earlier_ordinary_binding():
    cls = _build(
        "import fractions as order_b\ntry:\n    import decimal as order_b\nexcept ImportError:\n    order_b = None\n",
        'order_b.Decimal("2")',
    )
    assert cls().build_out() == "2"


def test_guarded_base_class_is_in_trusted_method_snapshot():
    import ast

    from lfx.custom.validate import prepare_global_scope

    plain = HEADER + "class Plain(Component):\n    pass\n"
    guarded = (
        "try:\n    from lfx.custom.custom_component.component import Component\n"
        "except ImportError:\n    Component = object\n"
        "class Guarded(Component):\n    pass\n"
    )
    plain_snapshot: dict = {}
    guarded_snapshot: dict = {}
    prepare_global_scope(ast.parse(plain), trusted_method_returns=plain_snapshot)
    prepare_global_scope(ast.parse(guarded), trusted_method_returns=guarded_snapshot)
    assert plain_snapshot
    assert guarded_snapshot == plain_snapshot


def test_fallback_can_read_earlier_top_level_constant():
    cls = _build(
        "fallback_value = None\n"
        "try:\n    import no_such_module_xyz_123 as optional_const\n"
        "except ImportError:\n    optional_const = fallback_value\n",
        "optional_const is None",
    )
    assert cls().build_out() == "True"


def test_fallback_reading_an_unbound_name_does_not_break_class_creation():
    cls = _build(
        "try:\n    import no_such_module_xyz_123 as optional_late\n"
        "except ImportError:\n    optional_late = defined_later\n"
        "defined_later = 1\n",
        "1",
    )
    assert cls().build_out() == "1"


def test_constant_does_not_overwrite_a_later_import_used_by_the_fallback():
    cls = _build(
        "fallback_module = None\n"
        "import fractions as fallback_module\n"
        "try:\n    import no_such_module_xyz_123 as optional_mod\n"
        "except ImportError:\n    optional_mod = fallback_module\n",
        "optional_mod.Fraction(1, 2)",
    )
    assert cls().build_out() == "1/2"


def test_guard_replacing_an_earlier_constant_is_not_undone():
    cls = _build(
        "optional_frac = None\ntry:\n    import fractions as optional_frac\nexcept ImportError:\n    pass\n",
        "self.HALF",
        extra="    HALF = optional_frac.Fraction(1, 2)\n",
    )
    assert cls().build_out() == "1/2"


def test_constant_after_an_earlier_definition_keeps_source_order():
    cls = _build(
        "def helper_name():\n    return 1\n"
        "helper_name = None\n"
        "try:\n    import fractions as frac_for_order\nexcept ImportError:\n    pass\n",
        "helper_name is None",
    )
    assert cls().build_out() == "True"


@pytest.mark.parametrize(
    "capture",
    [
        "CAPTURED = VALUE\n",
        "def helper(value=VALUE):\n    return value\nCAPTURED = helper()\n",
        "class Helper:\n    value = VALUE\nCAPTURED = Helper.value\n",
    ],
    ids=["assignment", "function-default", "class-attribute"],
)
def test_guard_preserves_earlier_constant_read(capture: str):
    cls = _build(
        f'VALUE = "before"\n{capture}VALUE = "after"\ntry:\n    import math\nexcept ImportError:\n    pass\n',
        "CAPTURED",
    )
    assert cls().build_out() == "before"


def test_guard_fallback_reads_reassigned_constant_after_earlier_capture():
    cls = _build(
        'VALUE = "before"\nCAPTURED = VALUE\nVALUE = "after"\n'
        "try:\n    import no_such_module_xyz_123 as optional_value\n"
        "except ImportError:\n    optional_value = VALUE\n",
        "(CAPTURED, optional_value)",
    )
    assert cls().build_out() == "('before', 'after')"


def test_helper_and_guard_fallback_read_reassigned_constant():
    cls = _build(
        'VALUE = "before"\ndef helper():\n    return VALUE\nVALUE = None\n'
        "try:\n    import no_such_module_xyz_123 as optional_value\n"
        "except ImportError:\n    optional_value = VALUE\n",
        "helper() is None and optional_value is None",
    )
    assert cls().build_out() == "True"


def test_guard_restores_repeated_import_after_deferred_assignment():
    cls = _build(
        "early_constant = None\nimport fractions as repeated_module\nrepeated_module = object()\n"
        "try:\n    import fractions as repeated_module\nexcept ImportError:\n    pass\n",
        "repeated_module.Fraction(1, 2)",
    )
    assert cls().build_out() == "1/2"


def test_guard_removes_exception_name_after_deferred_assignment():
    cls = _build(
        "early_constant = None\nimport_failure = object()\n"
        "try:\n    import no_such_module_xyz_123\nexcept ImportError as import_failure:\n    pass\n",
        '"import_failure" not in globals()',
    )
    assert cls().build_out() == "True"


def test_prepare_global_scope_preserves_earlier_constant_read():
    import ast

    from lfx.custom.validate import prepare_global_scope

    scope = prepare_global_scope(
        ast.parse(
            'VALUE = "before"\nCAPTURED = VALUE\nVALUE = "after"\n'
            "try:\n    import math\nexcept ImportError:\n    pass\n"
        )
    )
    assert scope["CAPTURED"] == "before"
    assert scope["VALUE"] == "after"


def test_guard_import_attribute_is_resolved_once(monkeypatch):
    import ast
    import sys
    from types import ModuleType

    from lfx.custom.validate import prepare_global_scope

    imported_values = []

    def read_attribute(name):
        if name != "value":
            raise AttributeError(name)
        value = object()
        imported_values.append(value)
        return value

    probe = ModuleType("guarded_replay_probe")
    probe.__getattr__ = read_attribute
    monkeypatch.setitem(sys.modules, probe.__name__, probe)
    scope = prepare_global_scope(
        ast.parse(
            "early_constant = None\n"
            "try:\n    from guarded_replay_probe import value as optional_value\n"
            "except ImportError:\n    optional_value = None\n"
            "captured_constant = early_constant\n"
        )
    )
    assert len(imported_values) == 1
    assert scope["optional_value"] is imported_values[0]


def test_skipped_guard_does_not_depend_on_the_module_logger(monkeypatch):
    import lfx.custom.validate as validate_module

    monkeypatch.setattr(validate_module, "logger", object())
    cls = _build(
        "try:\n    import no_such_module_xyz_123 as optional_logless\n"
        "except ImportError:\n    optional_logless = defined_after_guard\n"
        "defined_after_guard = 1\n",
        "1",
    )
    assert cls().build_out() == "1"


def test_guarded_langflow_import_uses_the_same_lfx_fallback_as_plain_imports():
    cls = _build(
        "try:\n    from langflow.schema.data import Data as GuardedData\nexcept ImportError:\n    GuardedData = None\n",
        "GuardedData is not None",
    )
    assert cls().build_out() == "True"


def test_bare_except_guard_is_supported():
    cls = _build(
        "try:\n    import no_such_module_xyz_123 as bare_opt\nexcept:  # noqa: E722\n    bare_opt = None\n",
        "bare_opt is None",
    )
    assert cls().build_out() == "True"


def test_handler_that_does_not_match_lets_the_error_surface():
    with pytest.raises(ValueError, match="no_such_module_xyz_123"):
        _build(
            "try:\n    import no_such_module_xyz_123 as wrong_handler\nexcept KeyError:\n    wrong_handler = None\n",
            "1",
        )


def test_else_branch_runs_when_the_import_succeeds():
    cls = _build(
        "try:\n    import fractions as frac_else\nexcept ImportError:\n    has_frac = False\n"
        "else:\n    has_frac = True\n",
        "has_frac",
    )
    assert cls().build_out() == "True"


def test_wildcard_guard_is_not_applied_instead_of_taking_the_fallback():
    # Wildcard imports are unsupported by the scope builder, so the guard is left unapplied
    # (as before) rather than wrongly running ``except ImportError`` while ``math`` exists.
    with pytest.raises(ValueError, match="wildcard_pi"):
        _build(
            "try:\n    from math import *  # noqa: F403\n    wildcard_pi = pi  # noqa: F405\n"
            "except ImportError:\n    wildcard_pi = None\n",
            "1",
            extra="    VALUE = wildcard_pi\n",
        )
