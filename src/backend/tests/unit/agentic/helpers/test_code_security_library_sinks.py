"""Generated component validation rejects library wrappers around code execution."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langflow.agentic.helpers.code_security import scan_code_security
from langflow.agentic.helpers.validation import validate_component_runtime

_EXECUTION_APIS = (
    ("jinja2", "Template"),
    ("jinja2", "Environment"),
    ("jinja2.environment", "Template"),
    ("jinja2.environment", "Environment"),
    ("jinja2.sandbox", "Environment"),
    ("jinja2.nativetypes", "NativeTemplate"),
    ("jinja2.nativetypes", "NativeEnvironment"),
    ("sympy", "sympify"),
    ("sympy", "S"),
    ("sympy", "lambdify"),
    ("sympy.core", "S"),
    ("sympy.core", "sympify"),
    ("sympy.core.sympify", "sympify"),
    ("sympy.core.sympify", "kernS"),
    ("sympy.parsing.sympy_parser", "parse_expr"),
    ("sympy.parsing.sympy_parser", "eval_expr"),
    ("sympy.parsing.sympy_parser", "sympify"),
    ("sympy.utilities.lambdify", "lambdify"),
)


@pytest.mark.parametrize(("module", "member"), _EXECUTION_APIS)
@pytest.mark.parametrize(
    "source",
    [
        "import {module} as library\nlibrary.{member}(source)",
        "from {module} import {member} as evaluate\nevaluate(source)",
        "from {module} import *\n{member}(source)",
        "import {module} as library\nevaluate = library.{member}\nevaluate(source)",
        "import {module} as library\nevaluators = [library.{member}]\nevaluators[0](source)",
        "import {module} as library\ngetattr(library, '{member}')(source)",
    ],
)
def test_rejects_library_execution_apis(module, member, source):
    result = scan_code_security(source.format(module=module, member=member))
    assert not result.is_safe
    assert any(member in violation for violation in result.violations)


@pytest.mark.parametrize("module", ["duckdb", "_duckdb"])
@pytest.mark.parametrize("source", ["import {module}", "import {module} as sql", "from {module} import connect"])
def test_rejects_embedded_sql_execution_modules(module, source):
    result = scan_code_security(source.format(module=module))
    assert not result.is_safe
    assert any(module in violation for violation in result.violations)


@pytest.mark.parametrize(
    "source",
    [
        "from jinja2.sandbox import SandboxedEnvironment\nresult = SandboxedEnvironment().from_string(source).render()",
        "from jinja2.sandbox import ImmutableSandboxedEnvironment\nresult = ImmutableSandboxedEnvironment()",
        "from sympy import Symbol\nx = Symbol('x')\nresult = x + 1",
        "import sympy as sp\nresult = sp.Symbol('x') + sp.Integer(2)",
        "from jinja2 import select_autoescape\nresult = select_autoescape()",
    ],
)
def test_preserves_sandboxed_templates_and_symbolic_operations(source):
    assert scan_code_security(source).is_safe


@pytest.mark.parametrize(
    "source",
    [
        "import jinja2\nresult = jinja2.Template(source)",
        "import sympy\nresult = sympy.sympify(source)",
        "import duckdb\nresult = duckdb.sql(source)",
    ],
)
async def test_runtime_validation_blocks_sinks_before_component_construction(source, monkeypatch):
    monkeypatch.setattr(
        "lfx.services.deps.get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True)),
    )
    builder = MagicMock(side_effect=AssertionError("unsafe code reached component construction"))
    monkeypatch.setattr("lfx.custom.utils.build_custom_component_template", builder)

    result = await validate_component_runtime(source, user_id="test-user")

    assert result is not None
    assert "failed security validation" in result
    builder.assert_not_called()
