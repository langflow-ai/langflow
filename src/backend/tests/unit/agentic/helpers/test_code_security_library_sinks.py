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
    ("jinja2.ext", "Environment"),
    ("jinja2.sandbox", "Environment"),
    ("jinja2.sandbox", "SandboxedEnvironment"),
    ("jinja2.sandbox", "ImmutableSandboxedEnvironment"),
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
    """Execution APIs stay blocked through imports, aliases, and indirect references."""
    result = scan_code_security(source.format(module=module, member=member))
    assert not result.is_safe
    assert any(member in violation for violation in result.violations)


@pytest.mark.parametrize("module", ["duckdb", "_duckdb", "sqlite3", "_sqlite3"])
@pytest.mark.parametrize("source", ["import {module}", "import {module} as sql", "from {module} import connect"])
def test_rejects_embedded_sql_execution_modules(module, source):
    """Reject both the public database modules and their native backends."""
    result = scan_code_security(source.format(module=module))
    assert not result.is_safe
    assert any(module in violation for violation in result.violations)


@pytest.mark.parametrize("package", ["langflow", "lfx"])
@pytest.mark.parametrize(
    "source",
    [
        "import {package}.services",
        "import {package}.services.deps as service_helpers",
        "from {package}.services.deps import get_settings_service",
        "from {package} import services as service_helpers",
        "import {package} as platform\nservice_helpers = platform.services",
        "import {package} as platform\nservice_helpers = getattr(platform, 'services')",
        "import {package} as platform\nservice_helpers = vars(platform)['services']",
        "from {package} import *\nservice_helpers = services",
    ],
)
def test_rejects_internal_platform_service_access(package: str, source: str) -> None:
    result = scan_code_security(source.format(package=package))

    assert not result.is_safe
    assert any(f"{package}.services" in violation for violation in result.violations)


@pytest.mark.parametrize("package", ["langflow", "lfx"])
@pytest.mark.parametrize("helper_path", ["utils.util", "base.data.utils"])
@pytest.mark.parametrize(
    "source",
    [
        "from {module} import get_settings_service as settings",
        "import {module} as helper\naccessor = helper.get_settings_service",
        "import {module} as helper\naccessor = getattr(helper, 'get_settings_service')",
        "import {module} as helper\naccessor = vars(helper)['get_settings_service']",
        "import {module} as helper\naccessor = vars(helper).get('get_settings_service')",
        "from {module} import *\naccessor = get_settings_service",
    ],
)
def test_rejects_platform_service_accessor_reexports(package: str, helper_path: str, source: str) -> None:
    module = f"{package}.{helper_path}"
    result = scan_code_security(source.format(module=module))

    assert not result.is_safe
    assert any("get_settings_service" in violation for violation in result.violations)


@pytest.mark.parametrize("package", ["langflow", "lfx"])
@pytest.mark.parametrize("helper_path", ["utils.util", "base.data.utils"])
@pytest.mark.parametrize(
    "use", ["modules = [helper]", "modules = {'helper': helper}", "def pick_helper():\n    return helper"]
)
def test_rejects_service_accessor_hosts_at_opaque_boundaries(package: str, helper_path: str, use: str) -> None:
    module = f"{package}.{helper_path}"
    result = scan_code_security(f"import {module} as helper\n{use}")

    assert not result.is_safe
    assert any(f"Indirect reference to restricted module '{module}'" in violation for violation in result.violations)


@pytest.mark.parametrize("package", ["langflow", "lfx"])
@pytest.mark.parametrize(
    ("helper_path", "member"), [("utils.util", "escape_json_dump"), ("base.data.utils", "normalize_text")]
)
def test_preserves_public_utility_from_service_accessor_host(package: str, helper_path: str, member: str) -> None:
    module = f"{package}.{helper_path}"
    source = f"from {module} import {member}\nimport {module} as helper\ntransform = helper.{member}"

    assert scan_code_security(source).is_safe


@pytest.mark.parametrize("package", ["langflow", "lfx"])
def test_preserves_public_component_imports(package: str) -> None:
    source = f"from {package}.custom import Component\nfrom {package}.io import Output"

    assert scan_code_security(source).is_safe


@pytest.mark.parametrize(
    "source",
    [
        "import logging.config",
        "import logging.config as config",
        "from logging.config import dictConfig",
        "from logging import config as log_config",
        "import logging as log\nconfig = log.config",
        "import logging\nconfig = getattr(logging, 'config')",
    ],
)
def test_rejects_logging_configuration_access(source: str) -> None:
    result = scan_code_security(source)

    assert not result.is_safe
    assert any("logging.config" in violation for violation in result.violations)


def test_preserves_component_logging() -> None:
    source = "import logging\nlogger = logging.getLogger(__name__)\nlogger.info('Component finished')"

    assert scan_code_security(source).is_safe


@pytest.mark.parametrize(
    "source",
    [
        "from sympy import Symbol\nx = Symbol('x')\nresult = x + 1",
        "import sympy as sp\nresult = sp.Symbol('x') + sp.Integer(2)",
        "from jinja2 import select_autoescape\nresult = select_autoescape()",
    ],
)
def test_preserves_symbolic_operations_and_template_configuration(source):
    """Safe symbolic construction and template configuration remain available."""
    assert scan_code_security(source).is_safe


@pytest.mark.parametrize("constructor", ["SandboxedEnvironment", "ImmutableSandboxedEnvironment"])
@pytest.mark.parametrize(
    "setup",
    [
        "from jinja2.sandbox import {constructor} as Environment\nenv = Environment()",
        "import jinja2.sandbox as sandbox\nenv = sandbox.{constructor}()",
        "import jinja2.sandbox as sandbox\nconstructors = [sandbox.{constructor}]\nenv = constructors[0]()",
    ],
)
def test_rejects_mutable_sandbox_before_rendering_external_template(constructor, setup):
    """A mutable sandbox cannot become a trusted route for rendering external templates."""
    code = (
        setup.format(constructor=constructor)
        + "\nenv.is_safe_attribute = lambda obj, attr, value: True"
        + "\nresult = env.from_string(source).render()"
    )

    result = scan_code_security(code)

    assert not result.is_safe
    assert any(constructor in violation for violation in result.violations)


@pytest.mark.parametrize(
    "source",
    [
        "import jinja2\nresult = jinja2.Template(source)",
        "from jinja2.sandbox import SandboxedEnvironment\nenv = SandboxedEnvironment()",
        "from jinja2.sandbox import ImmutableSandboxedEnvironment\nenv = ImmutableSandboxedEnvironment()",
        "import sympy\nresult = sympy.sympify(source)",
        "import duckdb\nresult = duckdb.sql(source)",
        "import sqlite3",
        "from lfx.services.deps import get_settings_service",
        "import logging.config",
    ],
)
async def test_runtime_validation_blocks_sinks_before_component_construction(source, monkeypatch):
    """Runtime validation rejects these APIs before constructing a component."""
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
